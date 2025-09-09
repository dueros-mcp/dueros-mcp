import asyncio
import json
import logging
import os
import shutil
import base64
import time
from contextlib import AsyncExitStack
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters  # MCP是Model Context Protocol的缩写，一个用于连接AI模型和工具的协议
from mcp.client.stdio import stdio_client  # MCP标准输入/输出客户端，用于与服务器通信
from mcp.client.streamable_http import streamablehttp_client  # StreamableHTTP客户端，用于与支持StreamableHTTP的服务器通信
from mcp.types import ImageContent, CallToolResult
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ImageUtils:
    """图片处理工具类，用于保存工具返回的图片"""
    
    @staticmethod
    def save_base64_image(base64_data: str, output_path: str, mime_type: str = "image/jpeg") -> bool:
        """保存base64编码的图片到文件"""
        try:
            image_data = base64.b64decode(base64_data)
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True
        except Exception as e:
            logging.error(f"Failed to save image to {output_path}: {e}")
            return False


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
        """检测传输类型（stdio或streamablehttp）"""
        # 如果配置中有url字段，检查是否指定了传输类型
        if "url" in self.config:
            # 检查配置中是否明确指定了传输类型
            transport_type = self.config.get("transport_type", "streamablehttp")
            if transport_type == "streamablehttp":
                return transport_type
            else:
                # 默认使用StreamableHTTP（更高效的传输协议）
                return "streamablehttp"
        # 如果配置中有command字段，则为stdio连接
        elif "command" in self.config:
            return "stdio"
        else:
            raise ValueError(f"无法确定服务器 {self.name} 的传输类型")

    async def initialize(self) -> None:
        """初始化服务器连接。"""
        try:
            if self.transport_type == "streamablehttp":
                await self._initialize_streamablehttp()
            else:
                await self._initialize_stdio()
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise



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

    async def _initialize_streamablehttp(self) -> None:
        """初始化StreamableHTTP连接"""
        from datetime import timedelta
        
        url = self.config["url"]
        headers = self.config.get("headers", {})
        timeout = timedelta(seconds=self.config.get("timeout", 30))
        read_timeout = timedelta(seconds=self.config.get("sse_read_timeout", 300))
        
        # 通过StreamableHTTP与MCP服务器建立连接
        streamablehttp_transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(
                url=url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=read_timeout
            )
        )
        read, write, _ = streamablehttp_transport  # StreamableHTTP返回三个值，第三个是session_id回调
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
    ) -> Any:
        """
        执行工具。

        参数:
            tool_name: 要执行的工具名称。
            arguments: 工具参数。

        返回:
            工具执行结果。

        异常:
            RuntimeError: 如果服务器未初始化。
            Exception: 如果工具执行失败。
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        logging.info(f"Executing {tool_name}...")
        # 通过MCP协议调用工具
        result = await self.session.call_tool(tool_name, arguments)
        return result

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

    def get_response(self, messages: list[dict[str, str]], tools: list[dict] = None) -> dict:
        """
        从LLM获取响应。

        参数:
            messages: 消息字典列表。
            tools: 可用工具列表（OpenAI格式）。

        返回:
            包含响应内容和工具调用信息的字典。

        异常:
            httpx.RequestError: 如果对LLM的请求失败。
        """
        client = OpenAI(api_key=self.api_key)
        
        # 构建API调用参数
        api_params = {
            "model": "gpt-4o",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        # 如果有工具，添加到参数中
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"
        
        response = client.chat.completions.create(**api_params)
        
        # 返回响应信息
        message = response.choices[0].message
        result = {
            "content": message.content,
            "tool_calls": message.tool_calls if hasattr(message, 'tool_calls') else None
        }
        
        return result


class ChatSession:
    """编排用户、LLM和工具之间的交互。"""

    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        self.servers: list[Server] = servers
        self.llm_client: LLMClient = llm_client

    def _convert_tools_to_openai_format(self, tools: list[Tool]) -> list[dict]:
        """
        将MCP工具转换为OpenAI工具格式。

        参数:
            tools: MCP工具列表。

        返回:
            OpenAI格式的工具列表。
        """
        openai_tools = []
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools

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

    async def process_llm_response(self, llm_response: dict) -> tuple[str, list[dict]]:
        """
        处理LLM的响应并在需要时执行工具。

        参数:
            llm_response: 来自LLM的响应字典。

        返回:
            元组：(响应内容, 工具调用结果列表)。
        """
        import json

        content = llm_response.get("content", "")
        tool_calls = llm_response.get("tool_calls", [])
        tool_results = []

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_arguments = json.loads(tool_call.function.arguments)
                    logging.info(f"Executing tool: {tool_name}")
                    logging.info(f"With arguments: {tool_arguments}")

                    # 在所有服务器中查找工具并执行
                    tool_executed = False
                    for server in self.servers:
                        tools = await server.list_tools()
                        if any(tool.name == tool_name for tool in tools):
                            try:
                                result = await server.execute_tool(
                                    tool_name, tool_arguments
                                )

                                if isinstance(result, dict) and "progress" in result:
                                    progress = result["progress"]
                                    total = result["total"]
                                    percentage = (progress / total) * 100
                                    logging.info(
                                        f"Progress: {progress}/{total} "
                                        f"({percentage:.1f}%)"
                                    )

                                # 处理工具返回的结果
                                tool_content = self._process_tool_result(result, tool_name)
                                
                                tool_results.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": tool_content
                                })
                                tool_executed = True
                                break
                            except Exception as e:
                                error_msg = f"Error executing tool: {str(e)}"
                                logging.error(error_msg)
                                tool_results.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": error_msg
                                })
                                tool_executed = True
                                break

                    if not tool_executed:
                        error_msg = f"No server found with tool: {tool_name}"
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": error_msg
                        })

                except json.JSONDecodeError as e:
                    error_msg = f"Invalid tool arguments: {str(e)}"
                    logging.error(error_msg)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": error_msg
                    })

        return content, tool_results

    def _process_tool_result(self, result: Any, tool_name: str) -> str:
        """
        处理工具执行结果，支持CallToolResult、ImageContent和其他类型。

        参数:
            result: 工具执行结果。
            tool_name: 工具名称。

        返回:
            处理后的结果字符串。
        """
        # 检查是否是CallToolResult类型
        if hasattr(result, 'content') and hasattr(result, 'isError'):
            # 处理MCP CallToolResult
            if result.isError:
                # 如果是错误结果，返回错误信息
                error_content = result.content[0] if result.content else None
                if error_content and hasattr(error_content, 'text'):
                    return f"工具执行错误: {error_content.text}"
                else:
                    return f"工具执行错误: {str(result.content)}"
            
            # 处理成功结果
            if result.content:
                # 检查内容中是否有图片
                for content_item in result.content:
                    if isinstance(content_item, ImageContent):
                        return self._process_image_content(content_item, tool_name)
                    elif hasattr(content_item, 'type') and content_item.type == 'image':
                        return self._process_image_content(content_item, tool_name)
                
                # 处理其他类型的内容
                text_results = []
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text_results.append(content_item.text)
                    else:
                        text_results.append(str(content_item))
                
                return "\n".join(text_results)
            else:
                return "工具执行完成，但无返回内容"
        
        elif isinstance(result, ImageContent):
            # 直接的ImageContent类型
            return self._process_image_content(result, tool_name)
        
        elif isinstance(result, dict):
            # 处理字典类型结果
            if "error" in result:
                return f"错误: {result['error']}"
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
        
        elif isinstance(result, (list, tuple)):
            # 处理列表类型结果
            if len(result) == 2 and result[0] == "images":
                # 处理MCP图片结果格式
                images = result[1]
                if images and isinstance(images[0], ImageContent):
                    return self._process_image_content(images[0], tool_name)
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        else:
            # 处理其他类型结果
            return str(result)
    
    def _process_image_content(self, image_content: ImageContent, tool_name: str) -> str:
        """
        处理ImageContent类型的图片内容。

        参数:
            image_content: ImageContent对象。
            tool_name: 工具名称。

        返回:
            处理后的结果字符串。
        """
        logging.info(f"Tool {tool_name} returned an image")
        
        # 保存图片到当前目录
        timestamp = int(time.time())
        image_filename = f"xiaodu_photo_{timestamp}.jpg"
        image_path = os.path.join(os.getcwd(), image_filename)
        
        if ImageUtils.save_base64_image(image_content.data, image_path, image_content.mimeType):
            logging.info(f"Image saved to: {image_path}")
            return f"拍照成功！图片已保存到: {image_path}\n图片类型: {image_content.mimeType}\n图片大小: {len(image_content.data)} bytes (base64编码)"
        else:
            return f"图片保存失败，但已接收到图片数据 ({len(image_content.data)} bytes)"

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

            # 转换为OpenAI格式的工具
            openai_tools = self._convert_tools_to_openai_format(all_tools)

            # 简化的系统消息，主要说明助手的能力
            system_message = (
                "You are a helpful assistant with access to various tools for smart device control, "
                "information retrieval, and other useful functions. "
                "Use the appropriate tools when needed to help the user accomplish their tasks. "
                "When you receive tool results, transform them into natural, conversational responses. "
                "For xiaodu_mcp_server tools, you can control smart devices, take photos, and make announcements. "
                "When tools return images (like photos from xiaodu_take_photo), the system will automatically save them to local files and provide you with the file path information. "
                "Always provide helpful and informative responses."
            )

            messages = [{"role": "system", "content": system_message}]

            # 显示可用工具信息
            print(f"\n=== MCP Chatbot Ready ===")
            print(f"Connected to {len(self.servers)} servers with {len(all_tools)} total tools")
            for server in self.servers:
                print(f"  - {server.name} ({server.transport_type})")
            print("Type 'quit' or 'exit' to end the session.")
            print("Images returned by tools (like xiaodu_take_photo) will be automatically saved to local files.\n")

            # 主交互循环
            while True:
                try:
                    user_input = input("You: ").strip()
                    if user_input.lower() in ["quit", "exit"]:
                        logging.info("\nExiting...")
                        break

                    messages.append({"role": "user", "content": user_input})

                    # 获取LLM响应，传入工具列表
                    llm_response = self.llm_client.get_response(messages, openai_tools)
                    content, tool_results = await self.process_llm_response(llm_response)

                    # 添加助手的响应（可能包含工具调用）
                    assistant_message = {"role": "assistant", "content": content}
                    if llm_response.get("tool_calls"):
                        assistant_message["tool_calls"] = llm_response["tool_calls"]
                    messages.append(assistant_message)

                    # 如果有工具调用，添加工具结果并获取最终响应
                    if tool_results:
                        logging.info(f"Tool execution completed, getting final response")
                        messages.extend(tool_results)
                        
                        # 获取最终响应
                        final_response = self.llm_client.get_response(messages, openai_tools)
                        final_content, _ = await self.process_llm_response(final_response)
                        
                        print(f"\nAssistant: {final_content}")
                        messages.append({"role": "assistant", "content": final_content})
                    else:
                        print(f"\nAssistant: {content}")
                        if not content:
                            # 如果没有内容，说明只有工具调用，需要等待工具结果
                            logging.info("No content in response, waiting for tool results")

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