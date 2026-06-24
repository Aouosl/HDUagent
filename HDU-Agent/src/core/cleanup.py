# src/core/cleanup.py
"""
数据库定期清理模块

- 删除超过保留期限的聊天消息（90天普通消息 / 7天直播日志）
- 通过 FastAPI lifespan 事件自动启动后台任务
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from src.core.database import SessionLocal
from src.core.models import ChatMessage

logger = logging.getLogger(__name__)

# 保留期限
MESSAGE_RETENTION_DAYS = 90       # 普通聊天消息保留90天
LIVE_LOG_RETENTION_DAYS = 7       # 直播日志保留7天
CLEANUP_INTERVAL_HOURS = 24       # 每24小时执行一次清理


def run_cleanup():
    """立即执行一次数据清理，删除过期消息"""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        message_cutoff = now - timedelta(days=MESSAGE_RETENTION_DAYS)
        log_cutoff = now - timedelta(days=LIVE_LOG_RETENTION_DAYS)

        # 删除过期普通消息
        deleted_messages = db.execute(
            delete(ChatMessage).where(
                ChatMessage.created_at < message_cutoff,
                ChatMessage.is_live_log == False
            )
        ).rowcount

        # 删除过期直播日志
        deleted_logs = db.execute(
            delete(ChatMessage).where(
                ChatMessage.created_at < log_cutoff,
                ChatMessage.is_live_log == True
            )
        ).rowcount

        db.commit()
        if deleted_messages or deleted_logs:
            logger.info(
                "数据清理完成：普通消息 %d 条，直播日志 %d 条",
                deleted_messages, deleted_logs
            )
    except Exception as e:
        db.rollback()
        logger.error("数据清理失败: %s", e)
    finally:
        db.close()


async def cleanup_loop():
    """后台循环：定期执行数据清理"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)
        try:
            # 在后台线程中运行同步清理
            await asyncio.to_thread(run_cleanup)
        except Exception as e:
            logger.error("清理任务异常: %s", e)
