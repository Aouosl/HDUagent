# src/Agent/base_worker.py
from abc import ABC, abstractmethod
from src.Agent.subagent.protocol import (AgentTaskRequest, AgentTaskResponse)


class BaseWorkerAgent(ABC):
    """所有子智能体的标准化基类"""

    name: str = "未命名智能体"
    description: str = "该智能体的能力描述，主智能体会根据此描述决定是否将任务路由给它"

    @abstractmethod
    def execute_task(self, request: AgentTaskRequest) -> AgentTaskResponse:
        """
        接收标准任务请求，执行内部逻辑，返回标准响应。
        子类必须实现此方法。
        """
        pass