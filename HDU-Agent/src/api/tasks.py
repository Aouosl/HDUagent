# src/api/tasks.py
"""任务管理 CRUD API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.models import Task, User
from src.core.schemas import TaskCreate, TaskUpdate, TaskResponse, TaskPaginatedResponse
from src.core.security import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的渗透测试任务"""
    task = Task(
        user_id=current_user.id,
        agent_name=task_in.agent_name,
        target=task_in.target,
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/", response_model=TaskPaginatedResponse)
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: Optional[str] = Query(None, description="按状态筛选：pending/running/completed/failed"),
    agent_name: Optional[str] = Query(None, description="按智能体名称筛选"),
):
    """获取当前用户的任务列表（分页）"""
    base_query = db.query(Task).filter(Task.user_id == current_user.id)

    if status:
        base_query = base_query.filter(Task.status == status)
    if agent_name:
        base_query = base_query.filter(Task.agent_name == agent_name)

    total = base_query.count()
    tasks = base_query\
        .order_by(Task.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    # 确保 attack_graph_data 为 dict 或 None
    items = []
    for t in tasks:
        graph = t.attack_graph_data
        items.append(TaskResponse(
            id=t.id,
            user_id=t.user_id,
            agent_name=t.agent_name,
            target=t.target,
            status=t.status,
            token_consumption=t.token_consumption,
            attack_graph_data=graph if graph and graph.get("nodes") else None,
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))

    return TaskPaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个任务详情"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    graph = task.attack_graph_data
    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        agent_name=task.agent_name,
        target=task.target,
        status=task.status,
        token_consumption=task.token_consumption,
        attack_graph_data=graph if graph and graph.get("nodes") else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新任务状态或数据"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = task_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    graph = task.attack_graph_data
    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        agent_name=task.agent_name,
        target=task.target,
        status=task.status,
        token_consumption=task.token_consumption,
        attack_graph_data=graph if graph and graph.get("nodes") else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除任务及其关联的漏洞数据"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    db.delete(task)
    db.commit()
    return None
