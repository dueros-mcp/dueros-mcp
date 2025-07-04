import asyncio
import json
import logging
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters  # MCP是Multimodal Community Protocol的缩写，一个用于连接AI模型和工具的协议
from mcp.client.stdio import stdio_client  # MCP标准输入/输出客户端，用于与服务器通信
from mcp.client.sse import sse_client  # SSE客户端，用于与支持SSE的服务器通信
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Configuration:
    """管理MCP客户端的配置和环境变量。"""

    def __init__(self) -> None:
        """使用环境变量初始化配置。"""
        self.load_env()
        self.api_key = os.getenv("LLM_API_KEY")

    @staticmethod
    def load_env() -> None:
        """从.env文件加载环境变量。"""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> dict[str, Any]:
        """
        从JSON文件加载服务器配置。

        参数:
            file_path: JSON配置文件的路径。

        返回:
            包含服务器配置的字典。

        异常:
            FileNotFoundError: 如果配置文件不存在。
            JSONDecodeError: 如果配置文件不是有效的JSON。
        """
        with open(file_path, "r") as f:
            config_content = f.read()
        
        # 替换环境变量占位符
        config_content = Configuration._substitute_env_vars(config_content)
        
        return json.loads(config_content)

    @staticmethod
    def _substitute_env_vars(content: str) -> str:
        """替换配置内容中的环境变量占位符"""
        import re
        
        def replace_env_var(match):
            var_name = match.group(1)
            env_value = os.getenv(var_name)
            if env_value is None:
                logging.warning(f"Environment variable {var_name} not found, using empty string")
                return ""
            return env_value
        
        # 匹配${VAR_NAME}格式的环境变量
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_env_var, content)

    @property
    def llm_api_key(self) -> str:
        """
        获取LLM API密钥。

        返回:
            字符串形式的API密钥。

        异常:
            ValueError: 如果在环境变量中找不到API密钥。
        """
        if not self.api_key:
            raise ValueError("LLM_API_KEY not found in environment variables")
        return self.api_key


class Server:
    """管理MCP服务器连接和工具执行。"""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name: str = name
        self.config: dict[str, Any] = config
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None  # MCP客户端会话，用于与服务器通信
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self.transport_type: str = self._detect_transport_type()

    def _detect_transport_type(self) -> str:
        """检测传输类型（stdio或sse）"""
        # 如果配置中有url字段，则为SSE连接
        if "url" in self.config:
            return "sse"
        # 如果配置中有command字段，则为stdio连接
        elif "command" in self.config:
            return "stdio"
        else:
            raise ValueError(f"无法确定服务器 {self.name} 的传输类型")

    async def initialize(self) -> None:
        """初始化服务器连接。"""
        try:
            if self.transport_type == "sse":
                await self._initialize_sse()
            else:
                await self._initialize_stdio()
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def _initialize_sse(self) -> None:
        """初始化SSE连接"""
        url = self.config["url"]
        headers = self.config.get("headers", {})
        timeout = self.config.get("timeout", 30)
        sse_read_timeout = self.config.get("sse_read_timeout", 300)
        
        # 通过SSE与MCP服务器建立连接
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(
                url=url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout
            )
        )
        read, write = sse_transport
        # 创建MCP客户端会话
        session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        self.session = session

    async def _initialize_stdio(self) -> None:
        """初始化stdio连接"""
        command = (
            shutil.which("npx")
            if self.config["command"] == "npx"
            else self.config["command"]
        )
        if command is None:
            raise ValueError("The command must be a valid string and cannot be None.")

        # 创建一个MCP服务器参数对象，用于配置服务器连接
        server_params = StdioServerParameters(
            command=command,
            args=self.config["args"],
            env={**os.environ, **self.config["env"]}
            if self.config.get("env")
            else None,
        )
        
        # 通过stdin/stdout与MCP服务器建立连接
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        # 创建MCP客户端会话
        session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        self.session = session

    async def list_tools(self) -> list[Any]:
        """
        列出服务器上可用的工具。

        返回:
            可用工具列表。

        异常:
            RuntimeError: 如果服务器未初始化。
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        # 通过MCP协议获取服务器上可用的工具列表
        tools_response = await self.session.list_tools()
        tools = []

        for item in tools_response:
            if isinstance(item, tuple) and item[0] == "tools":
                for tool in item[1]:
                    tools.append(Tool(tool.name, tool.description, tool.inputSchema))

        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """
        执行工具，带有重试机制。

        参数:
            tool_name: 要执行的工具名称。
            arguments: 工具参数。
            retries: 重试次数。
            delay: 重试间隔（秒）。

        返回:
            工具执行结果。

        异常:
            RuntimeError: 如果服务器未初始化。
            Exception: 如果工具执行在所有重试后失败。
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                # 通过MCP协议调用工具
                result = await self.session.call_tool(tool_name, arguments)

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """清理服务器资源。"""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


class Tool:
    """表示工具及其属性和格式化信息。"""

    def __init__(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        """
        为LLM格式化工具信息。

        返回:
            描述工具的格式化字符串。
        """
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {self.name}
Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""


class LLMClient:
    """管理与LLM提供商的通信。"""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key

    def get_response(self, messages: list[dict[str, str]]) -> str:
        """
        从LLM获取响应。

        参数:
            messages: 消息字典列表。

        返回:
            LLM的响应字符串。

        异常:
            httpx.RequestError: 如果对LLM的请求失败。
        """
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=4096
        )
        return response.choices[0].message.content


class ChatSession:
    """编排用户、LLM和工具之间的交互。"""

    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        self.servers: list[Server] = servers
        self.llm_client: LLMClient = llm_client

    async def cleanup_servers(self) -> None:
        """正确清理所有服务器。"""
        cleanup_tasks = []
        for server in self.servers:
            cleanup_tasks.append(asyncio.create_task(server.cleanup()))

        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str) -> str:
        """
        处理LLM的响应并在需要时执行工具。

        参数:
            llm_response: 来自LLM的响应。

        返回:
            工具执行结果或原始响应。
        """
        import json

        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                logging.info(f"Executing tool: {tool_call['tool']}")
                logging.info(f"With arguments: {tool_call['arguments']}")

                # 在所有服务器中查找工具并执行
                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )

                            if isinstance(result, dict) and "progress" in result:
                                progress = result["progress"]
                                total = result["total"]
                                percentage = (progress / total) * 100
                                logging.info(
                                    f"Progress: {progress}/{total} "
                                    f"({percentage:.1f}%)"
                                )

                            return f"Tool execution result: {result}"
                        except Exception as e:
                            error_msg = f"Error executing tool: {str(e)}"
                            logging.error(error_msg)
                            return error_msg

                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    async def start(self) -> None:
        """主聊天会话处理程序。"""
        try:
            # 初始化所有MCP服务器
            for server in self.servers:
                try:
                    await server.initialize()
                    logging.info(f"Successfully initialized server: {server.name} (type: {server.transport_type})")
                except Exception as e:
                    logging.error(f"Failed to initialize server {server.name}: {e}")
                    await self.cleanup_servers()
                    return

            # 收集所有服务器上可用的工具
            all_tools = []
            for server in self.servers:
                try:
                    tools = await server.list_tools()
                    all_tools.extend(tools)
                    logging.info(f"Server {server.name} has {len(tools)} tools available")
                except Exception as e:
                    logging.error(f"Failed to list tools for server {server.name}: {e}")

            tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])

            # 系统消息，指导LLM如何使用MCP工具
            system_message = (
                "You are a helpful assistant with access to these tools:\n\n"
                f"{tools_description}\n\n"
                "Choose the appropriate tool based on the user's question. "
                "If no tool is needed, reply directly.\n\n"
                "IMPORTANT: When you need to use a tool, you must ONLY respond with "
                "the exact JSON object format below, nothing else:\n"
                "{\n"
                '    "tool": "tool-name",\n'
                '    "arguments": {\n'
                '        "argument-name": "value"\n'
                "    }\n"
                "}\n\n"
                "After receiving a tool's response:\n"
                "1. Transform the raw data into a natural, conversational response\n"
                "2. Keep responses concise but informative\n"
                "3. Focus on the most relevant information\n"
                "4. Use appropriate context from the user's question\n"
                "5. Avoid simply repeating the raw data\n\n"
                "Special Notes:\n"
                "- For xiaodu_mcp_server tools, you can control smart devices, take photos, and make announcements\n"
                "- Always use the exact parameter names and formats specified in the tool descriptions\n"
                "- Some tools may require specific device identifiers (userid, cuid, client_id)\n\n"
                "Please use only the tools that are explicitly defined above."
            )

            messages = [{"role": "system", "content": system_message}]

            # 显示可用工具信息
            print(f"\n=== MCP Chatbot Ready ===")
            print(f"Connected to {len(self.servers)} servers with {len(all_tools)} total tools")
            for server in self.servers:
                print(f"  - {server.name} ({server.transport_type})")
            print("Type 'quit' or 'exit' to end the session.\n")

            # 主交互循环
            while True:
                try:
                    user_input = input("You: ").strip()
                    if user_input.lower() in ["quit", "exit"]:
                        logging.info("\nExiting...")
                        break

                    messages.append({"role": "user", "content": user_input})

                    # 获取LLM响应
                    llm_response = self.llm_client.get_response(messages)
                    logging.info("\nAssistant: %s", llm_response)

                    # 处理响应，可能涉及执行MCP工具
                    result = await self.process_llm_response(llm_response)

                    if result != llm_response:
                        messages.append({"role": "assistant", "content": llm_response})
                        messages.append({"role": "system", "content": result})

                        # 获取最终响应
                        final_response = self.llm_client.get_response(messages)
                        logging.info("\nFinal response: %s", final_response)
                        messages.append(
                            {"role": "assistant", "content": final_response}
                        )
                    else:
                        messages.append({"role": "assistant", "content": llm_response})

                except KeyboardInterrupt:
                    logging.info("\nExiting...")
                    break
                except Exception as e:
                    logging.error(f"Error during interaction: {e}")
                    print(f"Error: {e}")

        finally:
            # 确保在任何情况下都清理服务器
            await self.cleanup_servers()


async def main() -> None:
    """初始化并运行聊天会话。"""
    config = Configuration()
    # 加载MCP服务器配置
    server_config = config.load_config("servers_config.json")
    # 创建MCP服务器列表
    servers = [
        Server(name, srv_config)
        for name, srv_config in server_config["mcpServers"].items()
    ]
    llm_client = LLMClient(config.llm_api_key)
    # 创建聊天会话，连接LLM和MCP服务器
    chat_session = ChatSession(servers, llm_client)
    await chat_session.start()


if __name__ == "__main__":
    asyncio.run(main())