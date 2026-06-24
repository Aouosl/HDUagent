# server.py
import sys
import json
import asyncio
import time
import uuid
import logging
from pathlib import Path
from contextlib import asynccontextmanager
import uvicorn
from src.config.logging_config import setup_logging

# 在导入其他模块前初始化日志系统
setup_logging()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from src.api.user import router as user_router
from src.api.auth import router as auth_router
from src.api import agent_config
from src.config.settings import settings
from src.core.database import SessionLocal, get_db, engine
from src.core.models import User, ChatMessage, Task
from src.core.cleanup import run_cleanup, cleanup_loop
from src.core.task_executor import task_poller
from src.api.dashboard import router as dashboard_router
from src.api.tasks import router as tasks_router
from src.tools.base import live_log_queue_var, event_loop_var, user_id_var

logger = logging.getLogger(__name__)

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.Agent.manager.graph import app as agent_graph


# ==================== FastAPI 生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时执行的初始化与清理"""
    # 启动时立即执行一次数据清理
    print("[Startup] 执行数据库清理...")
    await asyncio.to_thread(run_cleanup)
    # 启动后台定时清理任务
    cleanup_task = asyncio.create_task(cleanup_loop())
    print("[Startup] 后台清理任务已启动（间隔24h）")
    # 启动任务调度执行器
    executor_task = asyncio.create_task(task_poller())
    print("[Startup] 任务调度执行器已启动（间隔10s，最多2并发）")
    yield
    # 关闭
    cleanup_task.cancel()
    executor_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="HDU-Agent Backend API",
    description="自动化渗透测试系统 API",
    version="1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(agent_config.router, prefix="/api/agents")
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(tasks_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 请求ID中间件 ====================
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """为每个请求注入唯一请求ID，便于日志追踪"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response



# ==================== 简易频率限制中间件 ====================
import threading
from collections import defaultdict

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()
_RATE_LIMIT_WINDOW = 60  # 时间窗口（秒）
_RATE_LIMIT_MAX_REQUESTS = 120  # 每窗口最大请求数

# 无需限流的路径前缀
_RATE_LIMIT_WHITELIST = {"/api/health", "/ws"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """简易滑动窗口频率限制，仅对API路径生效"""
    path = request.url.path
    # 跳过白名单路径和静态文件
    if any(path.startswith(prefix) for prefix in _RATE_LIMIT_WHITELIST):
        return await call_next(request)
    if not path.startswith("/api/"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    key = f"{client_ip}:{path}"

    with _rate_limit_lock:
        timestamps = _rate_limit_store[key]
        # 清理过期记录
        timestamps[:] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
        if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
        timestamps.append(now)

    return await call_next(request)

# ==================== 全局异常处理器 ====================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一HTTP异常响应格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理，避免500时暴露内部细节"""
    logger.exception("未处理的异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误，请稍后重试",
            "status_code": 500,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ==================== 健康检查 ====================
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查端点：验证数据库连接及服务状态"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "service": "HDU-Agent API",
        "version": "1.0",
        "database": db_status,
    }


# 全局任务字典
active_tasks: dict[str, asyncio.Task] = {}

# 直播日志批量写入配置
LIVE_LOG_FLUSH_INTERVAL = 2.0
LIVE_LOG_MAX_BATCH = 50


@app.get("/")
async def get_index():
    html_path = root_dir / "src" / "fronted" / "landing.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ==================== 聊天历史 ====================
@app.get("/api/chat/history")
def get_chat_history(request: Request, session_id: str = Query(...), db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"messages": []}

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")

        records = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.created_at.asc()).all()

        messages = [
            {"sender": r.sender, "content": r.content, "isLiveLog": r.is_live_log}
            for r in records
        ]
        return {"messages": messages}
    except JWTError:
        return {"messages": []}



@app.get("/api/chat/sessions")
def get_chat_sessions(request: Request, db: Session = Depends(get_db)):
    """获取当前用户的所有会话列表（按最近活跃排序）"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"sessions": []}
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")
        # 查询该用户所有不重复的 session_id，以及每个会话的最新时间
        sessions_query = db.query(
            ChatMessage.session_id,
            func.max(ChatMessage.created_at).label("updated_at")
        ).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.session_id.isnot(None)
        ).group_by(ChatMessage.session_id).order_by(desc("updated_at")).all()
        sessions = []
        for sess_id, updated_at in sessions_query:
            # 取该会话的第一条 user 消息作为标题
            first_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == sess_id,
                ChatMessage.user_id == user_id,
                ChatMessage.sender == "user"
            ).order_by(ChatMessage.created_at.asc()).first()
            title = first_msg.content[:30] if first_msg and first_msg.content else "新对话"
            sessions.append({
                "session_id": sess_id,
                "title": title,
                "updated_at": updated_at.isoformat() if updated_at else None
            })
        return {"sessions": sessions}
    except JWTError:
        return {"sessions": []}

def save_message_to_db(user_id: int, sender: str, content: str,
                       session_id: str = "default", is_live_log: bool = False):
    """保存单条消息到数据库（短连接模式：用完即还）"""
    db = SessionLocal()
    try:
        new_msg = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            sender=sender,
            content=content,
            is_live_log=is_live_log
        )
        db.add(new_msg)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"消息存库失败: {e}")
    finally:
        db.close()


def flush_live_logs(buffer: list[dict]):
    """批量写入直播日志到数据库（短连接模式：开→写→关）"""
    if not buffer:
        return
    db = SessionLocal()
    try:
        for item in buffer:
            db.add(ChatMessage(
                user_id=item["user_id"],
                session_id=item["session_id"],
                sender=item["sender"],
                content=item["content"],
                is_live_log=True
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"批量日志写入失败: {e}")
    finally:
        db.close()
    buffer.clear()



def _get_user_agent_config(user_id: int, provider: str = None, model: str = None, api_key: str = None):
    """从WebSocket消息 + 数据库回退，组装用户的LLM配置"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        user_api_keys = user.api_keys if user and user.api_keys else {}
        
        # 前端传来的 api_key 优先级最高
        final_provider = provider or settings.DEFAULT_PROVIDER
        final_model = model or settings.DEFAULT_MODEL
        
        if api_key:
            user_api_keys[final_provider] = api_key
        
        return final_provider, final_model, user_api_keys
    finally:
        db.close()

async def _websocket_auth(websocket: WebSocket):
    """WebSocket 鉴权：返回 (user, username) 或断开连接"""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少认证 token")
        return None, None

    db = SessionLocal()
    try:
        # 延迟导入避免循环依赖
        from src.core.security import get_current_user_ws
        user = await get_current_user_ws(token, db)
        if user is None:
            await websocket.close(code=4002, reason="无效或过期的 token")
            return None, None
        return user, user.username
    except Exception as e:
        print(f"WebSocket 鉴权异常: {e}")
        await websocket.close(code=4003, reason="鉴权失败")
        return None, None
    finally:
        db.close()


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    current_user, current_username = await _websocket_auth(websocket)
    if current_user is None:
        return

    current_user_id = current_user.id
    session_id = websocket.query_params.get("session_id", "default")
    agent_type = websocket.query_params.get("agent_type", "pentest")

    print(f"[+] 操作员 {current_username} 已连接 (agent={agent_type}, session={session_id})")

    live_log_buffer: list[dict] = []
    last_flush_time = time.time()

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "")

            # 保存用户消息（短连接）
            save_message_to_db(current_user_id, "user", user_message, session_id=session_id)

            # 从消息中提取用户配置的 provider/model/api_key
            msg_provider = data.get("provider")
            msg_model = data.get("model")
            msg_api_key = data.get("api_key")
            msg_agent_type = data.get("agent_type", agent_type)
            
            # 组装 LLM 配置（前端配置优先，数据库回退）
            provider, model, api_keys = _get_user_agent_config(
                current_user_id, msg_provider, msg_model, msg_api_key
            )
            
            inputs = {
                "messages": [{"role": "user", "content": user_message}],
                "agent_type": msg_agent_type,
                "user_id": current_user_id,
                "current_provider": provider,
                "current_model": model,
                "user_api_keys": api_keys,
            }
            print(f"[Config] provider={provider}, model={model}, agent_type={msg_agent_type}")

            tool_log_queue = asyncio.Queue()
            live_log_queue_var.set(tool_log_queue)
            event_loop_var.set(asyncio.get_running_loop())
            user_id_var.set(current_user_id)

            async def stream_live_logs():
                nonlocal last_flush_time
                while True:
                    msg = await tool_log_queue.get()
                    if msg is None:
                        break

                    live_log_buffer.append({
                        "user_id": current_user_id,
                        "session_id": session_id,
                        "sender": "subagent",
                        "content": msg,
                    })

                    now = time.time()
                    if len(live_log_buffer) >= LIVE_LOG_MAX_BATCH or (now - last_flush_time) >= LIVE_LOG_FLUSH_INTERVAL:
                        flush_live_logs(live_log_buffer)
                        last_flush_time = now

                    await websocket.send_json({
                        "type": "message",
                        "sender": "subagent",
                        "content": msg,
                        "isLiveLog": True
                    })

            log_task = asyncio.create_task(stream_live_logs())

            async def run_graph():
                async for output in agent_graph.astream(inputs):
                    for node_name, node_state in output.items():
                        if node_name == "manager":
                            latest_message = node_state['messages'][-1]
                            content = latest_message.content if hasattr(latest_message, 'content') else latest_message[1]
                            save_message_to_db(current_user_id, "manager", content, session_id=session_id)
                            await websocket.send_json({
                                "type": "message",
                                "sender": "manager",
                                "content": content,
                                "isLiveLog": False
                            })

            loop = asyncio.get_running_loop()
            main_task = loop.create_task(run_graph())
            active_tasks[session_id] = main_task

            try:
                await main_task
            except asyncio.CancelledError:
                cancel_msg = "⚠️ 任务已被用户强制终止"
                save_message_to_db(current_user_id, "system", cancel_msg, session_id=session_id)
                await websocket.send_json({
                    "type": "message", "sender": "system",
                    "content": cancel_msg, "isLiveLog": False
                })
            finally:
                active_tasks.pop(session_id, None)
                tool_log_queue.put_nowait(None)
                await log_task
                flush_live_logs(live_log_buffer)

    except WebSocketDisconnect:
        print(f"[-] 操作员 {current_username} 连接已断开")
    except Exception as e:
        error_msg = f"运行出错: {str(e)}"
        save_message_to_db(current_user_id, "error", error_msg, session_id=session_id)
        try:
            await websocket.send_json({"type": "error", "content": error_msg})
        except Exception:
            pass


@app.post("/api/chat/stop")
async def stop_chat(
    session_id: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]
    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    task = active_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled", "session_id": session_id}
    else:
        return {"status": "not_found_or_completed", "session_id": session_id}


app.mount("/", StaticFiles(directory="src/fronted", html=True), name="fronted")
app.include_router(user_router)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000)
