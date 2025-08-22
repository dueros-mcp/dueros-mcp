"""使用结构化输出的分类路由器智能体。"""

from typing import Dict, Any, Literal, List
from pydantic import BaseModel, Field
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
    BaseMessage,
)

from art_gallery_system.agents.base_agent import BaseAgent
from art_gallery_system.state import MultiAgentState
from art_gallery_system.configuration import Configuration
from art_gallery_system.utils import load_chat_model
from art_gallery_system.prompts import (
    STRUCTURED_CLASSIFICATION_SYSTEM_PROMPT,
    STRUCTURED_CLASSIFICATION_USER_PROMPT_TEMPLATE
)


class ClassificationSchema(BaseModel):
    """分析用户查询并根据内容进行路由。"""
    
    reasoning: str = Field(
        description="分类推理的详细步骤。"
    )
    classification: Literal["art_gallery", "chat"] = Field(
        description="查询的分类：'art_gallery' 表示艺术画廊相关，'chat' 表示通用对话或其他主题。"
    )
    confidence: float = Field(
        description="分类置信度（0.0 到 1.0）",
        ge=0.0,
        le=1.0
    )

def _build_classification_history(raw_messages: List[BaseMessage], max_turns: int = 20) -> List[BaseMessage]:
    """构造用于分类的安全历史：
    - 仅保留 HumanMessage 与不含 tool_calls 的 AIMessage
    - 仅保留最近 max_turns 轮（约等于 2*max_turns 条消息）
    """
    filtered: List[BaseMessage] = []
    for m in raw_messages:
        if isinstance(m, HumanMessage):
            filtered.append(HumanMessage(content=m.content))
        elif isinstance(m, AIMessage):
            if getattr(m, "tool_calls", None):
                continue
            filtered.append(AIMessage(content=m.content))
        # 跳过 ToolMessage 及其他类型

    if max_turns > 0:
        filtered = filtered[-2 * max_turns :]
    return filtered

class ClassificationRouterAgent(BaseAgent):
    """分类路由器智能体，使用结构化输出。"""
    
    def __init__(self):
        super().__init__("classification_router")
        self._setup_structured_llm()
    
    def _setup_structured_llm(self):
        """设置具备结构化输出能力的模型。"""
        configuration = Configuration.from_context()
        llm = load_chat_model(configuration.classification_model)
        self.llm_router = llm.with_structured_output(ClassificationSchema)
    
    async def process(self, state: MultiAgentState) -> Dict[str, Any]:
        """处理用户查询并进行分类。"""
        
        all_messages = state.messages if state.messages else None
        # print(f"messages: {all_messages}")
        # 剔除最后一个message
        history_content = all_messages[:-1]
        user_message = all_messages[-1]
                
        if not user_message:
            raise ValueError("Missing user_message in state.messages")
        
        
        # 使用prompts.py中定义的模板
        system_prompt = STRUCTURED_CLASSIFICATION_SYSTEM_PROMPT
        user_query = STRUCTURED_CLASSIFICATION_USER_PROMPT_TEMPLATE.format(user_query=user_message.content)

        try:
            # 使用安全历史（过滤工具相关内容）
            filtered_history = _build_classification_history(history_content, max_turns=20)

            lc_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_query),
                *filtered_history,
            ]

            result = await self.llm_router.ainvoke(lc_messages)
            
            classification_message = f"""分类结果：{result.classification}"""
            
            return {
                "agent_type": result.classification,
                "classification_confidence": result.confidence,
                "messages": [AIMessage(content=classification_message)],
                "last_active_agent": "classification_router"
            }
            
        except Exception as e:
            raise e


async def classification_router_node(state: MultiAgentState) -> Dict[str, Any]:
    """分类路由节点函数。"""
    agent = ClassificationRouterAgent()
    return await agent.process(state) 