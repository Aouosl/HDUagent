# src/core/schemas.py
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# ==================== 认证相关 ====================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    provider: str = Field(..., description="首选AI平台")
    api_key: Optional[str] = Field(None, description="用户API Key")


class UserLogin(BaseModel):
    username: str = Field(..., min_length=2)
    password: str = Field(..., min_length=6)
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ==================== 智能体配置 ====================
class AgentConfigBase(BaseModel):
    agent_name: str
    provider: Optional[str] = "openai"
    api_key: Optional[str] = ""
    model: Optional[str] = "gpt-4o"


class AgentConfigCreate(AgentConfigBase):
    pass


class AgentConfigResponse(AgentConfigBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ==================== 仪表盘 ====================
class DashboardSummary(BaseModel):
    security_score: int
    vulns_today: int
    active_agents: int
    token_usage: str


class VulnDistributionItem(BaseModel):
    value: int
    name: str


class AttackGraph(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class DashboardStatsResponse(BaseModel):
    summary: DashboardSummary
    vuln_distribution: List[VulnDistributionItem]
    attack_graph: AttackGraph


# ==================== 漏洞报告 ====================
class VulnReportItem(BaseModel):
    id: int
    vuln_name: str
    severity: str
    description: Optional[str] = None
    created_at: datetime
    target: str
    username: str
    model_config = ConfigDict(from_attributes=True)


class VulnReportPaginatedResponse(BaseModel):
    """漏洞列表分页响应"""
    total: int
    page: int
    page_size: int
    items: List[VulnReportItem]


# ==================== 任务管理 ====================
class TaskCreate(BaseModel):
    agent_name: str = Field(..., description="执行该任务的智能体")
    target: str = Field(..., description="目标（IP/域名/URL）")


class TaskUpdate(BaseModel):
    status: Optional[str] = Field(None, description="任务状态")
    token_consumption: Optional[int] = Field(None, description="累计消耗Token")
    attack_graph_data: Optional[Dict[str, Any]] = Field(None, description="攻击链路图数据")


class TaskResponse(BaseModel):
    id: int
    user_id: int
    agent_name: str
    target: str
    status: str
    token_consumption: int
    attack_graph_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskPaginatedResponse(BaseModel):
    """任务列表分页响应"""
    total: int
    page: int
    page_size: int
    items: List[TaskResponse]


# ==================== 用户画像 ====================
class UserPortrait(BaseModel):
    tech_stack: List[str] = Field(default_factory=list, description="擅长的技术领域")
    risk_level: str = Field(default="low", description="系统评估的风险等级")
    interest_tags: List[str] = Field(default_factory=list, description="用户感兴趣的话题标签")
    last_active_task: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UserInfoResponse(BaseModel):
    id: int
    username: str
    portrait: UserPortrait
    model_config = ConfigDict(from_attributes=True)


class UserPortraitUpdate(BaseModel):
    tech_stack: Optional[List[str]] = Field(None, description="追加或更新的技术栈")
    risk_level: Optional[str] = Field(None, description="更新系统风险评估等级")
    interest_tags: Optional[List[str]] = Field(None, description="追加的兴趣标签")
    last_active_task: Optional[str] = Field(None, description="最后活跃的任务")
    activity_score: Optional[int] = Field(None, description="活跃度评估")
    preference: Optional[Dict[str, Any]] = Field(None, description="用户的偏好设置")
