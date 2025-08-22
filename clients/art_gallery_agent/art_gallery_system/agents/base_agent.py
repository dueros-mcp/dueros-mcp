"""多智能体系统的基础智能体类。"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from art_gallery_system.state import MultiAgentState
from art_gallery_system.utils import load_chat_model
from art_gallery_system.configuration import Configuration


class BaseAgent(ABC):
    """基础智能体类。"""
    
    def __init__(self, name: str, tools: Optional[List] = None):
        self.name = name
        self.tools = tools or []
        self._model_cache = {} 
        
    @abstractmethod
    async def process(self, state: MultiAgentState) -> Dict[str, Any]:
        """处理用户请求的抽象方法。"""
        pass
        
    def get_model(self, temperature: float = 0.3) -> Any:
        """获取配置的模型，支持缓存。"""
        # 检查缓存
        cache_key = f"temp_{temperature}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        # 创建新模型
        configuration = Configuration.from_context()
        model = load_chat_model(configuration.model)
        if self.tools:
            model = model.bind_tools(self.tools)
        
        # 缓存模型
        self._model_cache[cache_key] = model
        return model
    
    def update_tools(self, new_tools: List) -> None:
        """更新工具列表并清除模型缓存。"""
        self.tools = new_tools
        # 清除模型缓存，因为工具变化了
        self._model_cache.clear()
        print(f"[{self.name}] 工具已更新，共 {len(new_tools)} 个工具")
        
    def format_system_message(self, prompt_template: str, **kwargs) -> str:
        """格式化系统提示词。"""
        return prompt_template.format(**kwargs)
    
    def _filter_messages(self, messages: List) -> List:
        """过滤消息，移除包含未完成工具调用的消息。"""
        filtered_messages = []
        
        for i, message in enumerate(messages):
            # 如果是AIMessage且包含工具调，但是下一步的工具调用没有结果，则跳过这条消息
            if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
                # 检查下一个消息是否是ToolMessage
                if i + 1 < len(messages) and isinstance(messages[i + 1], ToolMessage):
                    # 有对应的工具结果，保留这条消息
                    filtered_messages.append(message)
                else:
                    # 没有对应的工具结果，跳过这条消息
                    continue
            else:
                # 其他类型的消息直接保留
                filtered_messages.append(message)
        
        return filtered_messages
        
    async def call_model_with_prompt(
        self, 
        state: MultiAgentState,
        system_prompt: str,
        temperature: float = 0.3
    ) -> AIMessage:
        """使用指定提示词调用模型。"""
        model = self.get_model(temperature)
        
        # 过滤消息，移除未完成的工具调用
        filtered_messages = self._filter_messages(state.messages)
        
        messages = [
            {"role": "system", "content": system_prompt},
            *filtered_messages
        ]
        
        response = await model.ainvoke(messages)
        return response 