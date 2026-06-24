# src/config/logging_config.py
"""
应用日志配置

统一配置 logging 模块，解决 logger.info() 被静默丢弃的问题。
在 server.py 和 main.py 启动时调用 setup_logging() 即可。
"""
import os
import sys
import logging
from pathlib import Path


def setup_logging(
    level: int = None,
    log_file: str = None,
    log_format: str = None,
):
    """
    配置 Python logging 系统。

    - StreamHandler → stderr（控制台输出）
    - FileHandler → 持久化日志文件（可选）

    Args:
        level: 日志级别，默认 INFO（可通过 LOG_LEVEL 环境变量覆盖）
        log_file: 日志文件路径，默认项目根目录 logs/app.log
        log_format: 日志格式字符串
    """
    if level is None:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    if log_file is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = str(log_dir / "app.log")

    if log_format is None:
        log_format = "[%(asctime)s] [%(levelname)-7s] %(name)s | %(message)s"

    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有的处理器（避免重复配置）
    root_logger.handlers.clear()

    # StreamHandler → stderr
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # FileHandler → 持久化日志
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # 文件日志创建失败不应阻止程序启动
        print(f"[WARNING] 无法创建日志文件 {log_file}: {e}", file=sys.stderr)

    # 降低第三方库的日志噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    root_logger.info("日志系统初始化完成 (level=%s, file=%s)", logging.getLevelName(level), log_file)
