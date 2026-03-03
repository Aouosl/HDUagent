# src/core/llm_factory.py
from langchain_openai import ChatOpenAI
from src.config.settings import settings

# 兼容 OpenAI 格式的模型注册表
# 格式: "provider_name": "base_url"
# 注意：OpenAI 官方不需要配 base_url，所以填 None
PROVIDER_REGISTRY = {
    "openai": None,
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 通义千问 OpenAI 兼容地址
    "kimi": "https://api.moonshot.cn/v1",  # 月之暗面 OpenAI 兼容地址
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",  # 智谱 OpenAI 兼容地址
    "silicon": "https://api.siliconflow.cn/v1",  # 硅基流动接口 (支持百川/清言等大量开源模型)
}


def get_llm(provider: str = None, model_name: str = None, temperature: float = 0.7):
    """
    终极版大模型工厂：支持几乎所有兼容 OpenAI 格式的模型。
    """
    provider = provider or settings.DEFAULT_PROVIDER
    model_name = model_name or settings.DEFAULT_MODEL

    # 统一转换成小写，防止大小写错误
    provider = provider.lower()

    if provider in PROVIDER_REGISTRY:
        # 1. 获取对应的 API Key
        api_key = settings.API_KEYS.get(provider)
        if not api_key:
            raise ValueError(f"缺少 {provider.upper()}_API_KEY，请在 .env 中配置。")

        # 2. 获取对应的 Base URL
        base_url = PROVIDER_REGISTRY[provider]

        # 3. 统一使用 ChatOpenAI 实例化
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url  # 如果是 None，Langchain 会自动使用默认的 OpenAI 地址
        )

    # 如果遇到不兼容 OpenAI 格式的模型（比如早期的 Claude、百度文心），可以单独在这加 elif
    # elif provider == "anthropic":
    #     from langchain_anthropic import ChatAnthropic
    #     return ChatAnthropic(model=model_name, ...)

    else:
        raise ValueError(f"不支持的模型提供商: {provider}。请检查 PROVIDER_REGISTRY 字典。")