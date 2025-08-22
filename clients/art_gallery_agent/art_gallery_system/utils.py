"""多智能体系统的通用工具函数。"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


def load_chat_model(fully_specified_name: str):
    """根据完整名称加载聊天模型。

    Args:
        fully_specified_name: 形如 "provider/model-name" 的模型名

    Returns:
        已加载的聊天模型实例
    """
    if "/" not in fully_specified_name:
        raise ValueError(f"Model name must be in format 'provider/model-name', got: {fully_specified_name}")
    
    provider, model_name = fully_specified_name.split("/", 1)
    
    if provider == "openai":
        return ChatOpenAI(model=model_name)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_name)
    elif provider == "openrouter":
        # OpenRouter 使用 OpenAI 兼容的 API
        import os
        return ChatOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=model_name,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL"),
                "X-Title": os.getenv("OPENROUTER_SITE_NAME"),
            }
        )
    else:
        # Mock implementation for testing
        raise RuntimeError(
            "No supported LLM provider available for the specified model. "
            "Please install appropriate provider packages or configure langchain_community."
        )