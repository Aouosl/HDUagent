# src/Agent/protocol.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class AgentTaskRequest(BaseModel):
    """主智能体下发给子智能体的任务书"""
    task_id: str = Field(..., description="任务唯一标识")
    target: str = Field(..., description="任务目标（如 URL, IP, 文件路径）")
    intent: str = Field(..., description="具体的任务意图/指令")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="其他前置环境数据")

class AgentTaskResponse(BaseModel):
    """子智能体向上级汇报的结果"""
    status: str = Field(..., description="状态: success, failed, timeout")
    summary: str = Field(..., description="给主智能体阅读的高度概括摘要")
    raw_artifacts: Optional[Dict[str, Any]] = Field(None, description="结构化的漏洞数据或详细日志")
    error_msg: Optional[str] = Field(None, description="如果失败，提供错误信息")