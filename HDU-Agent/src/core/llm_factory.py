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
    # 注意：如果你的前端选项里有 anthropic，且你是通过 API 中转站访问的，可以把中转站的 base_url 加在这里
    # "anthropic": "https://api.your-proxy.com/v1" 
}

def get_llm(provider: str = None, model_name: str = None, temperature: float = 0.7, api_key: str = None):
    provider = provider or settings.DEFAULT_PROVIDER
    model_name = model_name or settings.DEFAULT_MODEL
    provider = provider.lower()

    if provider in PROVIDER_REGISTRY:
        # 【核心修改】直接使用传入的 api_key，彻底废弃 .env 全局配置回退
        if not api_key:
            raise ValueError(f"⚠️ 鉴权失败：缺少 {provider.upper()} 的 API Key。请在前端控制台点击「主模型配置」或「沙箱配置」录入您的专属 Key。")

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
    else:
        raise ValueError(f"不支持的模型提供商: {provider}。请检查 PROVIDER_REGISTRY 字典配置。")
