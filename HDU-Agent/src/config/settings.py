# src/config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

class Settings:
    # 默认选型
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    # API Keys 字典，方便后续按名字提取
    API_KEYS = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "qwen": os.getenv("QWEN_API_KEY"),
        "kimi": os.getenv("KIMI_API_KEY"),
        "zhipu": os.getenv("ZHIPU_API_KEY"),
        "silicon": os.getenv("SILICON_API_KEY"),
    }

settings = Settings()