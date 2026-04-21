# src/api/user.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any
from src.core.database import get_db
from src.core.models import User
from src.core.schemas import UserInfoResponse, UserPortraitUpdate, UserPortrait
# 假设你在 security.py 中实现了获取当前用户的依赖项
from src.core.security import get_current_user 

router = APIRouter(prefix="/api/user", tags=["User Profile"])

@router.get("/me", response_model=UserInfoResponse)
def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户的完整信息及画像"""
    # 处理默认 JSONB 数据映射到 Pydantic 模型
    portrait_dict = current_user.portrait_data if current_user.portrait_data else {}
    
    # 构建兼容 UserPortrait 模型的字典
    portrait_obj = UserPortrait(
        tech_stack=portrait_dict.get("tech_stack", []),
        risk_level=portrait_dict.get("risk_level", "low"),
        interest_tags=portrait_dict.get("interest_tags", []),
        last_active_task=portrait_dict.get("last_active_task")
    )
    
    return UserInfoResponse(
        id=current_user.id,
        username=current_user.username,
        portrait=portrait_obj
    )

@router.put("/me/portrait", response_model=UserInfoResponse)
def update_user_portrait(
    update_data: UserPortraitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动或由前端系统更新用户的画像字段"""
    # 获取现有的 JSONB 数据，由于设置了 server_default，安全起见先赋空字典
    current_portrait = current_user.portrait_data or {}
    
    # 提取更新数据中非 None 的字段
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # 针对列表类型的数据进行合并去重（例如 tech_stack 和 interest_tags）
    for list_key in ["tech_stack", "interest_tags"]:
        if list_key in update_dict:
            existing_list = current_portrait.get(list_key) or []
            new_items = update_dict[list_key]
            # 合并并去重
            current_portrait[list_key] = list(set(existing_list + new_items))
            update_dict.pop(list_key) # 处理完毕，移除
            
    # 针对其他普通字段直接覆盖更新
    current_portrait.update(update_dict)
    
    # 将更新后的字典重新赋值给 JSONB 字段
    current_user.portrait_data = current_portrait
    
    # 标记修改并提交到数据库
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(current_user, "portrait_data")
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # 返回更新后的最新信息
    return get_user_profile(current_user=current_user)
