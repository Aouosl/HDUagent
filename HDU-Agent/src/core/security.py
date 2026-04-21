# src/core/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from src.core.database import get_db

# 1. 优先从环境变量读取 SECRET_KEY，如果没有则使用备用值（确保本地开发能跑，生产环境防泄露）
SECRET_KEY = os.getenv("HDU_SECRET_KEY", "hdu_agent_super_secret_key_change_this_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # Token 7天有效

# 配置密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的 bcrypt 哈希值"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    
    # 修复 Python 3.12+ datetime.utcnow() 弃用警告
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """解析并验证 JWT 令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# ==========================================
# 依赖注入函数 (配合 FastAPI 的路由保护)
# ==========================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    用于普通 HTTP API 请求的鉴权。
    抛出 HTTPException 以便 FastAPI 直接返回 401 错误。
    """
    # 局部导入避免与 models 形成循环依赖
    from src.core.models import User 
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据或 Token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        
    return user

async def get_current_user_ws(token: str, db: Session):
    """
    专为 WebSocket 设计的鉴权。
    不抛出 HTTP 异常，而是返回 None，让外层决定是否 close()。
    """
    from src.core.models import User
    
    if not token:
        return None
        
    payload = decode_access_token(token)
    if not payload:
        return None
        
    username: str = payload.get("sub")
    if username is None:
        return None
        
    user = db.query(User).filter(User.username == username).first()
    return user
