# 示例：自动化画像更新服务
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from src.core.models import User

def auto_update_user_portrait(db: Session, user_id: int, detected_tags: list, last_task_name: str = None):
    """
    当大语言模型(LLM)识别出用户当前的对话意图，或是用户提交了新任务时，触发此函数自动完善画像。
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
        
    portrait = user.portrait_data or {}
    
    # 自动合并标签到画像中
    existing_tags = set(portrait.get("interest_tags", []))
    for tag in detected_tags:
        existing_tags.add(tag)
    portrait["interest_tags"] = list(existing_tags)
    
    if last_task_name:
        portrait["last_active_task"] = last_task_name
        # 简单的活跃度提升逻辑
        score = portrait.get("activity_score", 0)
        portrait["activity_score"] = score + 5
        
    user.portrait_data = portrait
    flag_modified(user, "portrait_data")
    db.commit()
