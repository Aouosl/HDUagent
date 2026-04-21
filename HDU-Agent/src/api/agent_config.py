# src/api/agent_config.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from src.core.database import get_db
from src.core.models import AgentConfig, User
from src.core.schemas import AgentConfigCreate
from src.core.security import SECRET_KEY, ALGORITHM

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 依赖注入：获取当前登录用户
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="凭证无效")
    except JWTError:
        raise HTTPException(status_code=401, detail="凭证无效")
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

@router.get("/config/{agent_name}")
async def get_agent_config(
    agent_name: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # [新增] 鉴权
):
    """获取指定智能体的配置，不存在则返回默认值"""
    config = db.query(AgentConfig).filter(
        AgentConfig.agent_name == agent_name,
        AgentConfig.user_id == current_user.id # [修改] 只查当前用户的
    ).first()
    
    if not config:
        return {"agent_name": agent_name, "api_key": "", "model": "gpt-4o"}
    
    return {
        "agent_name": config.agent_name,
        "api_key": config.api_key,
        "model": config.model
    }

@router.post("/config")
async def update_agent_config(
    config_in: AgentConfigCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # [新增] 鉴权
):
    """更新或创建智能体配置"""
    config = db.query(AgentConfig).filter(
        AgentConfig.agent_name == config_in.agent_name,
        AgentConfig.user_id == current_user.id # [修改] 只查当前用户的
    ).first()
    
    if config:
        config.api_key = config_in.api_key
        config.model = config_in.model
    else:
        config = AgentConfig(
            user_id=current_user.id, # [新增] 绑定用户 ID
            agent_name=config_in.agent_name,
            api_key=config_in.api_key,
            model=config_in.model
        )
        db.add(config)
    
    db.commit()
    return {"status": "success", "message": f"[{config_in.agent_name}] 配置已保存"}
