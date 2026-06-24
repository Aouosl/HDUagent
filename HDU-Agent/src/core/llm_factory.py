# src/core/llm_factory.py
from langchain_openai import ChatOpenAI
from src.config.settings import settings

# 模型提供商的 Base URL 注册表
PROVIDER_REGISTRY = {
    "openai": None,  # 官方 OpenAI 不需要 base_url
    "deepseek": "https://api.deepseek.com", # DeepSeek 官方建议的 base_url
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "silicon": "https://api.siliconflow.cn/v1",
}


def get_llm(provider: str = None, model_name: str = None, temperature: float = 0.7, api_key: str = None):
    """获取 LLM 实例
    
    API Key 优先级：
    1. 传入的 api_key 参数（用户前端配置）
    2. settings.API_KEYS 环境变量中的全局 Key
    3. 都没有则抛出错误
    """
    provider = (provider or settings.DEFAULT_PROVIDER).lower()
    model_name = model_name or settings.DEFAULT_MODEL
    
    # 决定使用的 API Key：用户Key > 全局环境变量Key
    if not api_key:
        api_key = settings.API_KEYS.get(provider)
    
    if not api_key:
        raise ValueError(
            f"缺少 {provider.upper()} 的 API Key。"
            f"请在 .env 中设置 {provider.upper()}_API_KEY 环境变量，"
            f"或在前端「配置中心」中录入您的专属 Key。"
        )

    if provider not in PROVIDER_REGISTRY:
        supported = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"不支持的模型提供商: {provider}。当前支持: {supported}")

    base_url = PROVIDER_REGISTRY[provider]

    # 动态构建 kwargs，避免给 ChatOpenAI 传入 base_url=None 导致底层报错
    kwargs = {
        "model": model_name,
        "temperature": temperature,
        "api_key": api_key,
    }
    
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
