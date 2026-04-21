# src/core/schemas.py
from pydantic import BaseModel,Field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
class UserCreate(BaseModel):
    username: str
    password: str
    provider: str  # 必填：用户注册时选择的首选平台
    api_key: Optional[str] = None  # 改回可选：允许暂不填写

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
class AgentConfigBase(BaseModel):
    agent_name: str
    provider: Optional[str] = "openai" 
    api_key: Optional[str] = ""
    model: Optional[str] = "gpt-4o"

class AgentConfigCreate(AgentConfigBase):
    pass

class AgentConfigResponse(AgentConfigBase):
    id: int
    class Config:
        from_attributes = True  # Pydantic V2 (如果报错请改为 orm_mode = True)

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



class VulnReportItem(BaseModel):
    id: int
    vuln_name: str
    severity: str
    description: Optional[str]
    created_at: datetime
    target: str      # 关联的 Task 目标
    username: str    # 关联的 User 名称

    class Config:
        from_attributes = True

class UserPortrait(BaseModel):
    tech_stack: List[str] = Field(default_factory=list, description="擅长的技术领域")
    risk_level: str = Field(default="low", description="系统评估的风险等级")
    interest_tags: List[str] = Field(default_factory=list, description="用户感兴趣的话题标签")
    last_active_task: Optional[str] = None
    
    class Config:
        from_attributes = True

# 扩展已有的 User 相关 Schema，或者新增一个查询接口使用
class UserInfoResponse(BaseModel):
    id: int
    username: str
    portrait: UserPortrait
    
    class Config:
        from_attributes = True

class UserPortraitUpdate(BaseModel):
    tech_stack: Optional[List[str]] = Field(None, description="追加或更新的技术栈")
    risk_level: Optional[str] = Field(None, description="更新系统风险评估等级")
    interest_tags: Optional[List[str]] = Field(None, description="追加的兴趣标签")
    last_active_task: Optional[str] = Field(None, description="最后活跃的任务")
    activity_score: Optional[int] = Field(None, description="活跃度评分")
    preference: Optional[Dict[str, Any]] = Field(None, description="用户的偏好设置(如语言等)")
