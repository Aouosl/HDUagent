# src/core/models.py
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Boolean, Index, func, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .database import Base


def _utcnow():
    """返回当前 UTC 时间，兼容 Python 3.11+"""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    api_keys = Column(JSONB, server_default=text("'{}'::jsonb"))
    portrait_data = Column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        comment="用户画像：技术栈、风险评估、偏好等"
    )
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    messages = relationship("ChatMessage", back_populates="owner")
    agent_configs = relationship("AgentConfig", back_populates="owner")
    tasks = relationship("Task", back_populates="owner")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    agent_name = Column(String, index=True, nullable=False, comment="智能体标签")
    api_key = Column(String, nullable=True, comment="用户专属 API Key")
    model = Column(String, default="gpt-4o", comment="使用的模型名称")
    provider = Column(String, default="openai", comment="模型提供商")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="agent_configs")

    # 复合唯一索引：同一用户下 agent_name 唯一
    __table_args__ = (
        Index("ix_agent_configs_user_agent", "user_id", "agent_name", unique=True),
    )

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, name='{self.agent_name}', user_id={self.user_id})>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    session_id = Column(
        String(100), index=True, nullable=True,
        comment="会话标识"
    )
    sender = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    is_live_log = Column(Boolean, default=False, comment="是否为终端实时日志")
    intent_tags = Column(JSONB, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime, default=_utcnow, index=True)

    owner = relationship("User", back_populates="messages")

    # 复合索引：加速按用户+会话查询历史消息
    __table_args__ = (
        Index("ix_chat_messages_user_session", "user_id", "session_id"),
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, sender='{self.sender}', session='{self.session_id}')>"


class AgentExperience(Base):
    """智能体经验记忆表"""
    __tablename__ = "agent_experiences"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(
        String(100), unique=True, index=True, nullable=False,
        comment="子智能体/工具名称"
    )
    learned_expertise = Column(
        Text, nullable=False,
        default="尚未积累经验，请基于默认设定使用。",
        comment="学习到的特长总结"
    )
    success_count = Column(Integer, default=0, comment="成功完成任务次数")
    fail_count = Column(Integer, default=0, comment="任务失败或用户不满意次数")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<AgentExperience(name='{self.agent_name}', success={self.success_count}, fail={self.fail_count})>"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    agent_name = Column(String(100), nullable=False, comment="执行该任务的智能体")
    target = Column(String(255), nullable=False, comment="目标(IP/域名/URL)")
    status = Column(String(50), default="pending", index=True)
    token_consumption = Column(Integer, default=0, comment="累计消耗Token")
    attack_graph_data = Column(
        JSONB,
        server_default=text("'{\"nodes\": [], \"edges\": []}'::jsonb"),
        comment="攻击链路图数据"
    )
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="tasks")
    vulnerabilities = relationship(
        "Vulnerability", back_populates="task",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Task(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class Vulnerability(Base):
    """漏洞资产表"""
    __tablename__ = "vulnerabilities"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    vuln_name = Column(String(255), nullable=False, comment="漏洞名称")
    severity = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True, comment="漏洞详情")
    created_at = Column(DateTime, default=_utcnow, index=True)

    task = relationship("Task", back_populates="vulnerabilities")

    def __repr__(self):
        return f"<Vulnerability(id={self.id}, name='{self.vuln_name}', severity='{self.severity}')>"
