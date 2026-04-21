# src/tools/base.py
from typing import Type, Any
from pydantic import BaseModel
from langchain_core.tools import BaseTool
import contextvars

live_log_queue_var = contextvars.ContextVar('live_log_queue_var', default=None)
event_loop_var = contextvars.ContextVar('event_loop_var', default=None)
user_id_var = contextvars.ContextVar('user_id_var', default=None)


class BaseSecurityTool(BaseTool):
    """
    所有安全工具的标准化基类
    """
    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel]

    def _run(self, **kwargs: Any) -> str:
        """同步执行逻辑，子类必须实现"""
        raise NotImplementedError("子类必须实现 _run 方法")

    def _arun(self, **kwargs: Any) -> str:
        """异步执行逻辑（如果需要的话）"""
        raise NotImplementedError("异步执行尚未实现")
