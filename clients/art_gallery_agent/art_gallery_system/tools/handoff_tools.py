"""用于多智能体间交接（handoff）的工具。"""

from typing import Annotated, Optional
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from art_gallery_system.state import MultiAgentState


def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """创建 handoff 工具，允许代理主动转移到其他代理。"""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer to {agent_name} for specialized assistance."

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MultiAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        reason: Optional[str] = None,
    ) -> Command:
        """handoff 工具实现。"""
        # 创建工具消息
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}" + (f" - {reason}" if reason else ""),
            "name": name,
            "tool_call_id": tool_call_id,
        }
        
        # 根据agent_name映射到严格的agent类型
        agent_type_mapping = {
            "art_gallery_agent_subgraph": "art_gallery",
            "chat_agent_subgraph": "chat"
        }
        agent_type = agent_type_mapping.get(agent_name, "chat")
        
        # 返回Command，包含状态更新和路由信息
        return Command(
            goto=agent_name,  # 目标agent
            update={
                "messages": state.messages + [tool_message],
                "last_active_agent": agent_name,
                "agent_type": agent_type,  # 使用映射后的严格agent类型
            },
            graph=Command.PARENT,  # 导航到父图
        )
    
    return handoff_tool


# 预定义的handoff工具 - 使用嵌套子图架构的节点名称
transfer_to_art_gallery = create_handoff_tool(
    agent_name="art_gallery_agent_subgraph",
    description="Transfer to the art gallery specialist for artwork queries, artist information, and art-related assistance."
)

transfer_to_chat = create_handoff_tool(
    agent_name="chat_agent_subgraph",
    description="Transfer to the general chat assistant for casual conversation and general assistance."
)

# 所有handoff工具列表
HANDOFF_TOOLS = [
    transfer_to_art_gallery,
    transfer_to_chat
] 