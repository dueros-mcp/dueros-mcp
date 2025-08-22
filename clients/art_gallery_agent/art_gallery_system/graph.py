"""定义带 Handoffs 路由的多智能体图，按智能体拆分为子图。

支持具备工具调用能力的聊天模型，并通过检查点机制提供短期记忆。
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast, Any
import asyncio

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from art_gallery_system.configuration import Configuration
from art_gallery_system.state import InputState, MultiAgentState
from art_gallery_system.utils import load_chat_model

from art_gallery_system.agents import (
    classification_router_node,
    art_gallery_agent_node,
    chat_agent_node,
)
from art_gallery_system.tools import ART_GALLERY_TOOLS
from art_gallery_system.tools import get_art_gallery_tools_with_mcp
    
    
# ----------- 预加载MCP工具 -----------
# 全局变量，将在异步初始化时设置
ART_GALLERY_TOOLS_WITH_MCP = ART_GALLERY_TOOLS

# ----------- 功能开关 -----------
# 是否启用在执行工具前的人参与审阅（Human-in-the-Loop）
ENABLE_HITL_TOOL_REVIEW = False

# ----------- 异步初始化函数 -----------
async def initialize_graph_tools():
    """异步初始化图工具"""
    global ART_GALLERY_TOOLS_WITH_MCP
    art_tools = await get_art_gallery_tools_with_mcp()
    ART_GALLERY_TOOLS_WITH_MCP = art_tools


# ----------- 子图构建函数 -----------
def build_art_gallery_agent_graph():
    """构建艺术画廊智能体子图"""
    builder = StateGraph(MultiAgentState, input=MultiAgentState, config_schema=Configuration)
    builder.add_node("art_gallery_agent", art_gallery_agent_node)
    
    # 使用预加载的工具列表（包含MCP工具）
    builder.add_node("art_tools", ToolNode(ART_GALLERY_TOOLS_WITH_MCP))
    
    # agent -> tools or end
    def route_tools(state: MultiAgentState):
        last_message = state.messages[-1]
        if not isinstance(last_message, AIMessage):
            return END
        if not getattr(last_message, "tool_calls", None):
            return END
        # 根据开关：是否进入人参与审阅
        return "pre_tool_review" if ENABLE_HITL_TOOL_REVIEW else "art_tools"
    
    # 条件边（基础映射始终包含 art_tools / END）
    cond_map = {"art_tools": "art_tools", END: END}
    if ENABLE_HITL_TOOL_REVIEW:
        # 在执行具体工具前的人参与审阅节点
        def pre_tool_review_node(state: MultiAgentState):
            last_message = state.messages[-1] if state.messages else None
            tool_calls = getattr(last_message, "tool_calls", None) or []
            summarized = []
            for tc in tool_calls:
                name = getattr(tc, "name", None) or (tc.get("name") if isinstance(tc, dict) else None)
                args = getattr(tc, "args", None) or (tc.get("args") if isinstance(tc, dict) else {})
                summarized.append({"name": name, "args": args})
            decision = interrupt({"proposed_tool_calls": summarized})
            approved = decision if isinstance(decision, bool) else bool((decision or {}).get("approved", True))
            return {"processed_data": {"tool_review": {"approved": approved}}}
        builder.add_node("pre_tool_review", pre_tool_review_node)
        cond_map["pre_tool_review"] = "pre_tool_review"
        # 审阅通过则调用工具；否则回到智能体节点重新规划
        def route_after_review(state: MultiAgentState):
            review = (state.processed_data or {}).get("tool_review", {}) if hasattr(state, "processed_data") else {}
            if not review.get("approved", True):
                return "art_gallery_agent"
            return "art_tools"
        builder.add_conditional_edges(
            "pre_tool_review",
            route_after_review,
            {"art_gallery_agent": "art_gallery_agent", "art_tools": "art_tools"},
        )

    builder.add_conditional_edges("art_gallery_agent", route_tools, cond_map)
    builder.add_edge("art_tools", "art_gallery_agent")
    builder.add_edge(START, "art_gallery_agent")
    return builder.compile(name="ArtGalleryAgentSubgraph")

def build_chat_agent_graph():
    builder = StateGraph(MultiAgentState, input=MultiAgentState, config_schema=Configuration)
    builder.add_node("chat_agent", chat_agent_node)
    builder.add_edge(START, "chat_agent")
    builder.add_edge("chat_agent", END)
    return builder.compile(name="ChatAgentSubgraph")

# ----------- 主流程（嵌套子图） -----------
def route_to_agent(state: MultiAgentState):
    agent_routing_map = {
        "art_gallery": "art_gallery_agent_subgraph",
        "chat": "chat_agent_subgraph"
    }
    return agent_routing_map.get(state.agent_type, "chat_agent_subgraph")

def build_multi_agent_graph_nested():
    """构建多智能体图（标准LangGraph方式）"""
    builder = StateGraph(MultiAgentState, input=InputState, config_schema=Configuration)
    builder.add_node("classification_router", classification_router_node)
    # 嵌入子图
    builder.add_node("art_gallery_agent_subgraph", build_art_gallery_agent_graph())
    builder.add_node("chat_agent_subgraph", build_chat_agent_graph())
    builder.add_edge(START, "classification_router")
    builder.add_conditional_edges(
        "classification_router",
        route_to_agent,
        {
            "art_gallery_agent_subgraph": "art_gallery_agent_subgraph",
            "chat_agent_subgraph": "chat_agent_subgraph"
        }
    )
    # 子图结束后直接结束
    builder.add_edge("art_gallery_agent_subgraph", END)
    builder.add_edge("chat_agent_subgraph", END)
    return builder

# ----------- 导出主图 -----------
# 初始化工具和图
asyncio.run(initialize_graph_tools())

# 构建并编译图（LangGraph API 会自动处理持久化）
builder = build_multi_agent_graph_nested()

graph = builder.compile(
    name="art_gallery_system",
) 