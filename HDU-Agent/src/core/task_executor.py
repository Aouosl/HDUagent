# src/core/task_executor.py
"""
后台任务执行器
- 轮询 pending 状态的任务并自动执行
- 通过 Agent Graph 运行渗透测试
- 更新任务状态、Token消耗、攻击链路图
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import update
from src.core.database import SessionLocal
from src.core.models import Task, User
from src.config.settings import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 10
MAX_CONCURRENT_TASKS = 2

# 正在运行的任务ID集合
_running_task_ids: set = set()


async def execute_single_task(task_id: int, user_id: int, agent_name: str, target: str):
    """执行单个任务，通过Agent Graph运行渗透测试"""
    from src.Agent.manager.graph import app as agent_graph
    
    db = SessionLocal()
    try:
        # 1. 标记为运行中
        db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(status="running", updated_at=datetime.now(timezone.utc))
        )
        db.commit()
        
        # 2. 获取用户API配置
        user = db.query(User).filter(User.id == user_id).first()
        user_api_keys = user.api_keys if user and user.api_keys else {}
        provider = settings.DEFAULT_PROVIDER
        model = settings.DEFAULT_MODEL
        if user_api_keys:
            provider = list(user_api_keys.keys())[0]
        
        # 3. 构建任务指令并运行Agent Graph
        task_message = f"对目标 {target} 执行自动化渗透测试。请使用 {agent_name} 进行深度安全扫描与漏洞挖掘。"
        
        inputs = {
            "messages": [{"role": "user", "content": task_message}],
            "user_id": user_id,
            "current_provider": provider,
            "current_model": model,
            "user_api_keys": user_api_keys,
        }
        
        logger.info(f"[TaskExecutor] 开始执行任务 #{task_id}: target={target}, agent={agent_name}")
        
        total_tokens = 0
        try:
            async for output in agent_graph.astream(inputs):
                for node_name, node_state in output.items():
                    if node_name == "manager":
                        latest_msg = node_state['messages'][-1]
                        if hasattr(latest_msg, 'response_metadata'):
                            meta = latest_msg.response_metadata
                            if 'token_usage' in meta:
                                total_tokens += meta['token_usage'].get('total_tokens', 0)
        except Exception as exec_err:
            logger.error(f"[TaskExecutor] Agent执行异常 #{task_id}: {exec_err}")
            raise
        
        # 4. 标记完成
        db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status="completed",
                token_consumption=Task.token_consumption + total_tokens,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        logger.info(f"[TaskExecutor] 任务 #{task_id} 执行完成, Token消耗: {total_tokens}")
        
    except Exception as e:
        logger.error(f"[TaskExecutor] 任务 #{task_id} 执行失败: {e}")
        try:
            db.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(status="failed", updated_at=datetime.now(timezone.utc))
            )
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
        _running_task_ids.discard(task_id)


def _start_task_execution(task: Task):
    """在事件循环中启动任务执行"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # 没有运行中的事件循环
    
    _running_task_ids.add(task.id)
    loop.create_task(execute_single_task(task.id, task.user_id, task.agent_name, task.target))


async def task_poller():
    """后台轮询：检查pending任务并执行"""
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        
        if len(_running_task_ids) >= MAX_CONCURRENT_TASKS:
            continue
        
        db = SessionLocal()
        try:
            available_slots = MAX_CONCURRENT_TASKS - len(_running_task_ids)
            tasks = db.query(Task).filter(
                Task.status == "pending"
            ).order_by(Task.created_at.asc()).limit(available_slots).all()
            
            for task in tasks:
                if task.id not in _running_task_ids:
                    _start_task_execution(task)
                    logger.info(f"[TaskPoller] 调度执行任务 #{task.id}: {task.target}")
        except Exception as e:
            logger.error(f"[TaskPoller] 轮询异常: {e}")
        finally:
            db.close()
