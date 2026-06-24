"""
数据库连接与会话管理模块

提供基于 SQLAlchemy 2.0+ 的数据库引擎、会话工厂和依赖注入函数。
数据库 URL 通过环境变量配置，支持连接池和自动重连。
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载 .env 文件（必须在 os.getenv 之前）
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# ---- 中文 Windows GBK 编码兼容 ----
# PostgreSQL 在中文 Windows 上的错误消息可能为 GBK 编码，
# psycopg2 默认按 UTF-8 解码会触发 UnicodeDecodeError (0xd6)。
# 这里 monkey-patch psycopg2.connect，将 GBK 错误消息转为可读的中文。
if sys.platform == "win32":
    os.environ["PGCLIENTENCODING"] = "UTF8"

    import psycopg2
    _original_connect = psycopg2.connect

    def _safe_connect(dsn=None, *args, **kwargs):
        try:
            return _original_connect(dsn, *args, **kwargs)
        except UnicodeDecodeError as e:
            raw_bytes = e.object if hasattr(e, 'object') else b''
            try:
                msg = raw_bytes.decode('gbk', errors='replace')
            except Exception:
                msg = str(raw_bytes)
            raise ConnectionError(
                f"PostgreSQL 连接失败（服务器返回中文错误）:\n{msg}"
            ) from e

    psycopg2.connect = _safe_connect

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase

# 数据库连接 URL 从环境变量读取（.env 已在上面加载）
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@127.0.0.1:54321/hdu_agent_db"
)

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    connect_args={
        "options": "-c client_encoding=UTF8",
    },
)

# 会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# ORM 模型基类
class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束时自动关闭"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
