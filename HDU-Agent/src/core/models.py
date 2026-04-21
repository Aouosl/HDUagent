# src/core/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, text,Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    # [新增] 绑定具体的所属用户
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True) 
    
    # [修改] 去掉 unique=True，因为不同用户可以有同名的 agent 配置
    agent_name = Column(String, index=True, nullable=False, comment="智能体标识(如: pentestagent, webctfagent)")
    api_key = Column(String, nullable=True, comment="用户为此智能体配置的专属 API Key")
    model = Column(String, default="gpt-4o", comment="使用的模型名称")
    provider = Column(String, default="openai", comment="模型提供商")  
    # 可选：建立关系
    owner = relationship("User", backref="agent_configs")
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # 存储用户的私有大模型 API Keys
    api_keys = Column(JSONB, server_default=text("'{}'::jsonb")) 
    
    # --- [新增] 用户画像数据 ---
    # 存储结构建议：
    # {
    #   "tech_stack": ["web", "pwn"],          # 擅长领域
    #   "risk_level": "low",                  # 风险等级评估
    #   "preference": {"language": "zh"},     # 交互偏好
    #   "activity_score": 85                  # 活跃度评分
    # }
    portrait_data = Column(JSONB, server_default=text("'{}'::jsonb"), comment="用户画像：技术栈、风险评估、偏好等")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("ChatMessage", back_populates="owner")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 新增：用于支持同一个用户有多个不同的对话标签页/会话
    session_id = Column(String(100), index=True, nullable=True, comment="会话标识")
    
    # 消息发送者："user", "manager", "pentest_agent", "error", "system"
    sender = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    
    # 新增：用于标记这条消息是否是 Docker 沙箱的实时终端输出
    is_live_log = Column(Boolean, default=False, comment="是否为终端实时日志")
    
    # 专为未来“用户画像”设计的意图标签字段
    intent_tags = Column(JSONB, server_default=text("'[]'::jsonb"))
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # 建立与用户的多对一关系
    owner = relationship("User", back_populates="messages")

class AgentExperience(Base):
    """
    智能体经验记忆表
    用于 Manager 学习并记录各个子智能体擅长的领域
    """
    __tablename__ = "agent_experiences"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(100), unique=True, index=True, nullable=False, comment="子智能体/工具名称")
    
    # 核心字段：由大模型不断总结和更新的文本
    learned_expertise = Column(Text, nullable=False, default="尚未积累经验，请基于默认设定使用。", comment="学习到的特长总结")
    
    # 统计数据，可以用来辅助判断
    success_count = Column(Integer, default=0, comment="成功完成任务次数")
    fail_count = Column(Integer, default=0, comment="任务失败或用户不满意次数")
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(100), nullable=False, comment="执行该任务的智能体")
    target = Column(String(255), nullable=False, comment="目标(IP/域名/URL)")
    
    status = Column(String(50), default="pending", index=True)
    
    # [新增] 记录当前任务消耗的总 Token 数
    token_consumption = Column(Integer, default=0, comment="累计消耗Token")
    
    # [新增] 记录当前的攻击链路图状态
    # 默认结构: {"nodes": [], "edges": []}
    attack_graph_data = Column(JSONB, server_default='{"nodes": [], "edges": []}', comment="攻击链路图数据")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", backref="tasks")


class Vulnerability(Base):
    """
    漏洞资产表
    用于记录 Agent 扫描或挖掘出来的漏洞，供大盘统计
    """
    __tablename__ = "vulnerabilities"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    vuln_name = Column(String(255), nullable=False, comment="漏洞名称")
    # 严重程度: "critical", "high", "medium", "low"
    severity = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True, comment="漏洞详情")

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联到产生此漏洞的任务
    task = relationship("Task", backref="vulnerabilities")
