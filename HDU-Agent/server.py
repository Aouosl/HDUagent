# server.py
import sys
import json
import asyncio
from pathlib import Path
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from src.api.user import router as user_router
from src.api.auth import router as auth_router
from src.api import agent_config
from src.core.security import SECRET_KEY, ALGORITHM
from src.core.database import SessionLocal, get_db
from src.core.models import User, ChatMessage
from sqlalchemy import func, desc
from src.api.dashboard import router as dashboard_router
from src.tools.base import live_log_queue_var, event_loop_var, user_id_var

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

pentest_agent_dir = root_dir / "src" / "Agent" / "subagent" / "pentest_agent" / "pentest-agent"
if str(pentest_agent_dir) not in sys.path:
    sys.path.insert(0, str(pentest_agent_dir))

from src.Agent.manager.graph import app as agent_graph

app = FastAPI(title="HDU-Agent Backend API", description="自动化渗透测试系统 API", version="1.0")

app.include_router(auth_router)
app.include_router(agent_config.router, prefix="/api/agents")
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局任务字典，用于存储正在执行的图任务（session_id -> asyncio.Task）
active_tasks: dict[str, asyncio.Task] = {}

@app.get("/")
async def get_index():
    html_path = root_dir / "src" / "fronted" / "landing.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# ================= [新增] 历史记录拉取接口 =================
@app.get("/api/chat/history")
def get_chat_history(request: Request, session_id: str = Query(...), db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"messages": []}
    
    token = auth_header.split(" ")[1]
    try:
        # 验证身份
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # 按时间顺序查询该用户的指定会话记录
        records = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        messages = []
        for r in records:
            messages.append({
                "sender": r.sender,
                "content": r.content,
                "isLiveLog": r.is_live_log
            })
        return {"messages": messages}
    except JWTError:
        return {"messages": []}

# ✅ 修复：增加 session_id 和 is_live_log 参数，兼容数据库新字段
def save_message_to_db(user_id: int, sender: str, content: str, session_id: str = "default", is_live_log: bool = False):
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
        print(f"消息存库失败: {e}")
    finally:
        db.close()

# ================= [新增/优化] 获取用户的历史会话列表 =================
@app.get("/api/chat/sessions")
def get_chat_sessions(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"sessions": []}
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # 优化 1：使用数据库层面的 GROUP BY 聚合并获取最新更新时间
        # 优化 2：强制 LIMIT 50，只拉取用户最近活跃的 50 个会话（防止海量数据）
        session_stats = db.query(
            ChatMessage.session_id,
            func.max(ChatMessage.created_at).label('updated_at')
        ).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.is_live_log == False
        ).group_by(
            ChatMessage.session_id
        ).order_by(
            desc('updated_at')
        ).limit(50).all()

        if not session_stats:
            return {"sessions": []}

        session_ids = [s.session_id for s in session_stats]

        # 优化 3：使用子查询，仅查询这 50 个 session_id 的“第一条 user 消息”作为标题
        # 找到每个 session最早的 user 消息的时间
        subq = db.query(
            ChatMessage.session_id,
            func.min(ChatMessage.created_at).label('min_time')
        ).filter(
            ChatMessage.session_id.in_(session_ids),
            ChatMessage.sender == 'user'
        ).group_by(
            ChatMessage.session_id
        ).subquery()

        # 关联主表，提取内容
        first_messages = db.query(
            ChatMessage.session_id,
            ChatMessage.content
        ).join(
            subq,
            (ChatMessage.session_id == subq.c.session_id) & 
            (ChatMessage.created_at == subq.c.min_time)
        ).all()

        # 将标题映射到字典 O(1) 查找
        title_map = {}
        for msg in first_messages:
            title_map[msg.session_id] = msg.content[:15] + ("..." if len(msg.content) > 15 else "")

        # 组装最终结果
        sessions_list = []
        for s in session_stats:
            sessions_list.append({
                "session_id": s.session_id,
                "title": title_map.get(s.session_id, "新对话"),
                "updated_at": s.updated_at.timestamp() if s.updated_at else 0
            })
        
        return {"sessions": sessions_list}
        
    except JWTError:
        return {"sessions": []}

@app.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket, token: str = Query(None)):
    if not token:
        await websocket.close(code=1008, reason="Missing Token")
        return

    db = SessionLocal()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == token_user_id).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
            
        current_user_id = user.id
        current_username = user.username
        db_api_keys = dict(user.api_keys) if user.api_keys else {}
        
    except JWTError:
        await websocket.close(code=1008, reason="Invalid Token")
        return
    finally:
        db.close()

    await websocket.accept()
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            
            provider, model, custom_api_key, session_id = None, None, None, "default"
            try:
                data = json.loads(raw_data)
                user_input = data.get("content", "")
                provider = data.get("provider")
                model = data.get("model")
                custom_api_key = data.get("api_key")
                session_id = data.get("session_id", f"default_{current_username}")
            except json.JSONDecodeError:
                user_input = raw_data
            
            # 1. 存入用户消息
            save_message_to_db(current_user_id, "user", user_input, session_id=session_id)
            
            # 2. 从数据库动态拉取此 session_id 的上下文给模型
            db = SessionLocal()
            chat_history = []
            try:
                history_records = db.query(ChatMessage).filter(
                    ChatMessage.user_id == current_user_id,
                    ChatMessage.session_id == session_id,
                    ChatMessage.is_live_log == False # 不把冗长的终端日志喂给模型，省钱且防干扰
                ).order_by(ChatMessage.created_at).all()
                
                for msg in history_records:
                    if msg.sender == "user":
                        chat_history.append(("user", msg.content))
                    elif msg.sender == "manager":
                        chat_history.append(("assistant", msg.content))
            finally:
                db.close()
            
            active_keys = db_api_keys.copy()
            if provider and custom_api_key:
                active_keys[provider] = custom_api_key
                if active_keys != db_api_keys:
                    try:
                        db_update = SessionLocal()
                        user_to_update = db_update.query(User).filter(User.id == current_user_id).first()
                        if user_to_update:
                            user_to_update.api_keys = active_keys
                            db_update.commit()
                            db_api_keys = active_keys # 更新内存中的引用
                    except Exception as e:
                        print(f"更新主控 API Key 失败: {e}")
                    finally:
                        db_update.close()
            
            current_provider = provider or "deepseek"
            
            if not active_keys.get(current_provider):
                err_msg = f"⚠️ 鉴权拦截：未检测到 {current_provider.upper()} 的 API Key。请点击右上角「主模型配置」按钮录入您的专属 Key。"
                save_message_to_db(current_user_id, "error", err_msg, session_id=session_id)
                await websocket.send_json({"type": "message", "sender": "error", "content": err_msg})
                await websocket.send_json({"type": "status", "content": "在线就绪"})
                continue  

            inputs = {
                "messages": chat_history,
                "user_api_keys": active_keys,
                "current_provider": current_provider,
                "current_model": model,
                "user_id": current_user_id
            }

            await websocket.send_json({"type": "status", "content": "🧠 凌霄 主控调度中..."})

            # ================= [绝密核心] 异步队列与并发推流架构 =================
            tool_log_queue = asyncio.Queue()
            live_log_queue_var.set(tool_log_queue)
            event_loop_var.set(asyncio.get_running_loop())
            user_id_var.set(current_user_id)

            async def stream_live_logs():
                while True:
                    msg = await tool_log_queue.get()
                    if msg is None: 
                        break
                    
                    # 💡 可选：如果你希望刷新后也能看到终端黑框日志，可以把这里解开存库
                    save_message_to_db(current_user_id, "pentest_agent", msg, session_id=session_id, is_live_log=True)
                    
                    await websocket.send_json({
                        "type": "message", 
                        "sender": "pentest_agent", 
                        "content": msg,
                        "isLiveLog": True
                    })

            log_task = asyncio.create_task(stream_live_logs())
            
            # 定义实际运行 agent_graph.astream 的协程
            async def run_graph():
                async for output in agent_graph.astream(inputs):
                    for node_name, node_state in output.items():
                        if node_name == "manager":
                            latest_message = node_state['messages'][-1]
                            content = latest_message.content if hasattr(latest_message, 'content') else latest_message[1]
                            
                            # 3. 存入智能体的最终答复
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
                cancel_msg = "⏹️ 任务已被用户强制终止"
                save_message_to_db(current_user_id, "system", cancel_msg, session_id=session_id)
                await websocket.send_json({
                    "type": "message",
                    "sender": "system",
                    "content": cancel_msg,
                    "isLiveLog": False
                })
            finally:
                # 清理任务字典
                active_tasks.pop(session_id, None)
                tool_log_queue.put_nowait(None)
                await log_task
            # ===================================================================

            await websocket.send_json({"type": "status", "content": "在线就绪"})

    except WebSocketDisconnect:
        print(f"[-] 操作员 {current_username} 连接已断开")
    except Exception as e:
        error_msg = f"运行出错: {str(e)}"
        save_message_to_db(current_user_id, "error", error_msg, session_id=session_id)
        try:
            await websocket.send_json({"type": "error", "content": error_msg})
        except:
            pass

@app.post("/api/chat/stop")
async def stop_chat(
    session_id: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """强制停止指定会话的正在执行的任务"""
    # 鉴权（与 WebSocket 逻辑一致）
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        # 可选：验证该 session_id 是否属于该用户，此处略（可由前端保证）
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
