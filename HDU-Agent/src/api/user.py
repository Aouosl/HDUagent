# src/api/user.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from src.core.database import get_db
from src.core.models import User
from src.core.schemas import UserInfoResponse, UserPortraitUpdate, UserPortrait
from src.core.security import get_current_user

router = APIRouter(prefix="/api/user", tags=["User Profile"])


@router.get("/me", response_model=UserInfoResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的完整信息及画像"""
    portrait_dict = current_user.portrait_data if current_user.portrait_data else {}

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
    current_portrait = current_user.portrait_data or {}
    update_dict = update_data.model_dump(exclude_unset=True)

    # 列表类型字段合并去重
    for list_key in ["tech_stack", "interest_tags"]:
        if list_key in update_dict:
            existing_list = current_portrait.get(list_key) or []
            new_items = update_dict[list_key]
            current_portrait[list_key] = list(set(existing_list + new_items))
            update_dict.pop(list_key)

    # 普通字段直接覆盖
    current_portrait.update(update_dict)
    current_user.portrait_data = current_portrait

    # 标记 JSONB 字段已修改
    flag_modified(current_user, "portrait_data")

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return get_user_profile(current_user=current_user)
