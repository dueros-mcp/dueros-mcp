"""定义多智能体系统的状态结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Optional, Dict, Any, List

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated


@dataclass
class InputState:
    """代理的输入状态，对外部接口进行窄化。

    用于定义初始状态与输入数据的结构。
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    用于跟踪代理的主要执行状态。

    常见模式：
    1）HumanMessage：用户输入
    2）带 tool_calls 的 AIMessage：选择并调用工具
    3）ToolMessage：工具执行结果或错误
    4）不带 tool_calls 的 AIMessage：回复用户
    5）HumanMessage：下一轮用户输入

    其中 2-5 可按需循环。`add_messages` 注解会按 ID 合并消息，
    在无重复 ID 的情况下维持追加式状态。
    """


@dataclass
class State(InputState):
    """代理的完整状态，在 `InputState` 基础上扩展额外字段。"""

    is_last_step: IsLastStep = field(default=False)
    """
    指示当前步骤是否为最后一步（图将抛出错误前）。

    该字段由状态机管理，当步数达到 recursion_limit - 1 时为 True。
    """


@dataclass
class MultiAgentState(InputState):
    """多智能体系统的状态结构 - 支持Handoffs模式"""
    
    # 路由信息
    agent_type: Optional[str] = None  # "art_gallery", "chat"
    classification_confidence: float = 0.0
    
    # Handoffs模式支持
    last_active_agent: str = "classification_router"  # 记录最后活跃的agent
    
    # 搜索结果缓存
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # 用户交互状态
    pending_question: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # 设备推送状态
    push_status: Dict[str, bool] = field(default_factory=dict)
    
    # 对话上下文
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    
    # 控制流程状态
    is_last_step: IsLastStep = field(default=False)
    
    # 中间处理结果
    processed_data: Dict[str, Any] = field(default_factory=dict) 