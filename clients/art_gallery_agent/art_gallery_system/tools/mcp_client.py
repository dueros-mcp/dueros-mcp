"""基于 langchain_mcp_adapters 的 MCP 客户端工具。"""

import asyncio
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from art_gallery_system.configuration import Configuration

@dataclass
class XiaoduDevice:
    """小度设备信息。"""
    cuid: str
    client_id: str
    name: str
    online: bool


class MCPClientManager:
    """MCP 客户端管理器，使用 langchain_mcp_adapters。"""
    
    def __init__(self):
        self.config = Configuration.from_context()
        self._mcp_client: Optional[MultiServerMCPClient] = None
        self._tools: Optional[List[BaseTool]] = None
    
    def _build_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """构建已处理环境变量的 MCP 服务器配置。"""
        mcp_servers: Dict[str, Dict[str, Any]] = {}
        for server_name, server_config in self.config.mcp_servers.items():
            processed_config = server_config.copy()
            # 处理headers中的环境变量占位符 ${VAR}
            if "headers" in processed_config:
                headers = processed_config["headers"].copy()
                for key, value in headers.items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]  # 移除 ${ 和 }
                        headers[key] = os.getenv(env_var, "")
                processed_config["headers"] = headers
            mcp_servers[server_name] = processed_config
        return mcp_servers
        
    async def _get_mcp_client(self) -> MultiServerMCPClient:
        """获取或创建 MCP 客户端。"""
        if self._mcp_client is None:
            # 处理环境变量替换
            mcp_servers = {}
            for server_name, server_config in self.config.mcp_servers.items():
                processed_config = server_config.copy()
                
                # 处理headers中的环境变量
                if "headers" in processed_config:
                    headers = processed_config["headers"].copy()
                    for key, value in headers.items():
                        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                            env_var = value[2:-1]  # 移除 ${ 和 }
                            headers[key] = os.getenv(env_var, "")
                    processed_config["headers"] = headers
                
                mcp_servers[server_name] = processed_config
            # 创建MultiServerMCPClient（不再作为上下文管理器）
            self._mcp_client = MultiServerMCPClient(mcp_servers)
            
        return self._mcp_client
    
    async def get_tools(self) -> List[BaseTool]:
        """获取 MCP 服务器提供的所有工具。"""
        if self._tools is None:
            client = await self._get_mcp_client()
            self._tools = await client.get_tools()

        return self._tools
    
    async def close(self):
        """关闭 MCP 客户端连接。"""
        # MultiServerMCPClient 不需要显式关闭
        self._mcp_client = None
        self._tools = None


# 全局客户端管理器实例
_mcp_client_manager: Optional[MCPClientManager] = None


def get_mcp_client_manager() -> MCPClientManager:
    """获取 MCP 客户端管理器实例。"""
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()
    return _mcp_client_manager


async def get_mcp_tools() -> List[BaseTool]:
    """获取所有 MCP 工具。"""
    manager = get_mcp_client_manager()
    return await manager.get_tools()


async def get_tools() -> List[BaseTool]:
    """向后兼容别名：获取所有 MCP 工具。"""
    return await get_mcp_tools()

async def close_mcp_client():
    """关闭 MCP 客户端连接。"""
    global _mcp_client_manager
    if _mcp_client_manager:
        await _mcp_client_manager.close()
        _mcp_client_manager = None 