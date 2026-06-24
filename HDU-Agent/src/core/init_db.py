# src/core/init_db.py
"""
数据库初始化模块

用于创建所有已定义的表结构。
仅在首次部署或模型变更时使用（生产环境建议使用 Alembic 迁移）。
"""
import time
import logging
from sqlalchemy.exc import OperationalError, DatabaseError
from src.core.database import engine, Base
# 导入所有模型，确保它们注册到 Base.metadata
from src.core.models import (   # noqa: F401
    User, AgentConfig, ChatMessage, AgentExperience, Task, Vulnerability
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY = 3  # 秒


def init_db():
    """连接数据库并创建所有表结构，失败时自动重试"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("正在连接数据库并创建表结构... (尝试 %d/%d)", attempt, MAX_RETRIES)
            Base.metadata.create_all(bind=engine)
            logger.info("数据库初始化完成。")
            return
        except (OperationalError, DatabaseError) as e:
            logger.warning(
                "数据库连接失败 (尝试 %d/%d): %s", attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                logger.info("等待 %d 秒后重试...", RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("数据库初始化失败，已重试 %d 次。", MAX_RETRIES)
                raise


if __name__ == "__main__":
    init_db()
