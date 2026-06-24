# src/core/security.py
"""
认证与安全模块

- 密码哈希：使用 bcrypt (2b 格式)
- JWT 令牌：创建、解码、验证
- FastAPI 依赖注入：HTTP / WebSocket 鉴权
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.config.settings import settings

# JWT 配置
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# OAuth2 方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# bcrypt 密码长度上限（72 字节）
_BCRYPT_MAX_LENGTH = 72


def _truncate_password(password: str) -> bytes:
    """将密码截断到 bcrypt 的 72 字节上限并编码为 UTF-8"""
    return password.encode("utf-8")[:_BCRYPT_MAX_LENGTH]


def get_password_hash(password: str) -> str:
    """生成密码的 bcrypt 哈希值"""
    return bcrypt.hashpw(_truncate_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return bcrypt.checkpw(_truncate_password(plain_password), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """解析并验证 JWT 令牌，失败返回 None"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ==================== 依赖注入 ====================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """HTTP API 鉴权依赖"""
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
    """WebSocket 鉴权（返回 None 表示失败，不抛异常）"""
    from src.core.models import User

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    username: str = payload.get("sub")
    if username is None:
        return None

    return db.query(User).filter(User.username == username).first()
