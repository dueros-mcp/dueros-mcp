"""通用聊天智能体。"""

from typing import Dict, Any, cast, Optional
from langchain_core.messages import AIMessage
from art_gallery_system.agents.base_agent import BaseAgent
from art_gallery_system.state import MultiAgentState
from art_gallery_system.prompts import CHAT_SYSTEM_PROMPT
from art_gallery_system.tools.handoff_tools import transfer_to_art_gallery


class ChatAgent(BaseAgent):
    """通用聊天智能体，支持 Handoffs 模式。"""
    
    def __init__(self):
        super().__init__("chat", [transfer_to_art_gallery])
        
    async def process(self, state: MultiAgentState) -> Dict[str, Any]:
        """处理通用聊天与对话。"""
        
        system_prompt = self.format_system_message(
            CHAT_SYSTEM_PROMPT,
            conversation_context=state.conversation_context
        )
        
        response = cast(
            AIMessage,
            await self.call_model_with_prompt(
                state, 
                system_prompt, 
                temperature=0.7  # 较高温度让对话更自然
            )
        )
        
        # 更新对话上下文
        updated_context = state.conversation_context.copy()
        updated_context["last_interaction"] = "chat"
        updated_context["topic"] = self._extract_topic(response.content)
        
        return {
            "messages": [response],
            "conversation_context": updated_context,
            "last_active_agent": "chat_agent"
        }
    
    def _extract_topic(self, content: str) -> str:
        """从回复中提取话题关键词。"""
        # 简化的话题提取逻辑
        if len(content) > 20:
            return content[:20] + "..."
        return content


# 全局智能体实例
_chat_agent: Optional[ChatAgent] = None


def get_chat_agent() -> ChatAgent:
    """获取全局聊天智能体实例。"""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent()
    return _chat_agent


async def chat_agent_node(state: MultiAgentState) -> Dict[str, Any]:
    """聊天智能体节点函数（使用全局实例）。"""
    agent = get_chat_agent()
    return await agent.process(state) 