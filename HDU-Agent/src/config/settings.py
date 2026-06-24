# src/config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    """应用全局配置，所有敏感信息通过 .env 环境变量管理"""

    # ==================== 数据库 ====================
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hdu_admin:hdu_agent@127.0.0.1:54321/hdu_agent_db")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

    # ==================== AI 平台默认值 ====================
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    # ==================== API Keys ====================
    API_KEYS = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "qwen": os.getenv("QWEN_API_KEY"),
        "kimi": os.getenv("KIMI_API_KEY"),
        "zhipu": os.getenv("ZHIPU_API_KEY"),
        "silicon": os.getenv("SILICON_API_KEY"),
    }

    # ==================== JWT ====================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


settings = Settings()
