"""多智能体系统的工具集合。"""

from .art_gallery_tools import (
    ART_GALLERY_TOOLS,
    get_art_gallery_tools_with_mcp
)
from .handoff_tools import (
    transfer_to_art_gallery,
    transfer_to_chat,
    HANDOFF_TOOLS
)
from .mcp_client import (
    MCPClientManager,
    XiaoduDevice,
    get_mcp_client_manager,
    get_mcp_tools,
    close_mcp_client
)
__all__ = [
    # 艺术画廊工具
    "ART_GALLERY_TOOLS",
    "get_art_gallery_tools_with_mcp",
    
    # Handoff工具
    "transfer_to_art_gallery",
    "transfer_to_chat",
    "HANDOFF_TOOLS",
    
    # MCP客户端（使用langchain_mcp_adapters）
    "MCPClientManager",
    "XiaoduDevice", 
    "get_mcp_client_manager",
    "get_mcp_tools",
    "close_mcp_client"
] 