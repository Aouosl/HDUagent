# src/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.models import User
from src.core.schemas import UserCreate, UserLogin, TokenResponse
from src.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register")
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="该操作员代号已被注册")

    # 构建个人的 API Key 配置字典
    keys_config = {}
    if user_data.api_key:  # 只有填写了才存入
        keys_config[user_data.provider] = user_data.api_key

    new_user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        api_keys=keys_config
    )
    db.add(new_user)
    db.commit()
    return {"message": "注册成功，请登录"}

@router.post("/login", response_model=TokenResponse)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="凭证错误：用户名或口令不正确"
        )
    
    # 生成 JWT Token
    access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
