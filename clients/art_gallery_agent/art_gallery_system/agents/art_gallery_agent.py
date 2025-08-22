"""艺术画廊智能体（处理画作相关查询）。"""

from typing import Dict, Any, cast, Literal, Optional
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from art_gallery_system.agents.base_agent import BaseAgent
from art_gallery_system.state import MultiAgentState
from art_gallery_system.prompts import ART_GALLERY_SYSTEM_PROMPT
from art_gallery_system.tools import get_art_gallery_tools_with_mcp


class ArtGalleryAgent(BaseAgent):
    """艺术画廊智能体，支持 Handoffs 与 Command，动态加载 MCP 工具。"""
    
    def __init__(self):
        # 初始化时不绑定工具，稍后异步加载
        super().__init__("art_gallery", [])
        self._tools_loaded = False
        
    async def _ensure_tools_loaded(self):
        """确保工具已加载。"""
        if not self._tools_loaded:
            # 动态获取包含MCP工具的工具列表
            tools = await get_art_gallery_tools_with_mcp()
            self.update_tools(tools)
            self._tools_loaded = True
            
    async def refresh_tools(self):
        """刷新工具列表（适用于 MCP 服务器更新）。"""
        tools = await get_art_gallery_tools_with_mcp()
        self.update_tools(tools)
        self._tools_loaded = True
        print(f"[{self.name}] 工具已刷新，共 {len(tools)} 个工具")
        
    async def process(self, state: MultiAgentState) -> Dict[str, Any]:
        """处理艺术画作相关的查询。"""
        
        await self._ensure_tools_loaded()
        
        system_prompt = self.format_system_message(
            ART_GALLERY_SYSTEM_PROMPT,
            user_preferences=state.user_preferences
        )
        
        response = cast(
            AIMessage,
            await self.call_model_with_prompt(
                state, 
                system_prompt, 
                temperature=0.3
            )
        )
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                if 'transfer_to_' in tool_call.get('name', ''):
                    return {
                        "messages": [response],
                        "last_active_agent": "art_gallery_agent"
                    }
        
        if state.is_last_step and hasattr(response, 'tool_calls') and response.tool_calls:
            return {
                "messages": [
                    AIMessage(
                        id=response.id,
                        content="抱歉，我无法在指定的步数内完成艺术作品查询，请尝试更具体的描述。",
                    )
                ],
                "last_active_agent": "art_gallery_agent"
            }
        
        return {
            "messages": [response],
            "last_active_agent": "art_gallery_agent"
        }


_art_gallery_agent: Optional[ArtGalleryAgent] = None

def get_art_gallery_agent() -> ArtGalleryAgent:
    """获取全局艺术画廊智能体实例。"""
    global _art_gallery_agent
    if _art_gallery_agent is None:
        _art_gallery_agent = ArtGalleryAgent()
    return _art_gallery_agent


async def art_gallery_agent_node(state: MultiAgentState) -> Dict[str, Any]:
    """艺术画廊智能体节点函数（使用全局实例）。"""
    agent = get_art_gallery_agent()
    return await agent.process(state) 