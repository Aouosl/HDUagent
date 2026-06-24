# src/api/agent_config.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.models import AgentConfig, User
from src.core.schemas import AgentConfigCreate
from src.core.security import get_current_user

router = APIRouter()


@router.get("/config/{agent_name}")
async def get_agent_config(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定智能体的配置，不存在则返回默认值"""
    config = db.query(AgentConfig).filter(
        AgentConfig.agent_name == agent_name,
        AgentConfig.user_id == current_user.id
    ).first()

    if not config:
        return {"agent_name": agent_name, "api_key": "", "model": "gpt-4o", "provider": "openai"}

    return {
        "agent_name": config.agent_name,
        "api_key": config.api_key,
        "model": config.model,
        "provider": config.provider
    }


@router.post("/config")
async def update_agent_config(
    config_in: AgentConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新或创建智能体配置"""
    config = db.query(AgentConfig).filter(
        AgentConfig.agent_name == config_in.agent_name,
        AgentConfig.user_id == current_user.id
    ).first()

    if config:
        config.api_key = config_in.api_key
        config.model = config_in.model
        config.provider = config_in.provider
    else:
        config = AgentConfig(
            user_id=current_user.id,
            agent_name=config_in.agent_name,
            api_key=config_in.api_key,
            model=config_in.model,
            provider=config_in.provider
        )
        db.add(config)

    db.commit()
    return {"status": "success", "message": f"[{config_in.agent_name}] 配置已保存"}
