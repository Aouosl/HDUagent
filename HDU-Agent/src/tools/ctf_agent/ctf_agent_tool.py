# HDU-Agent/src/tools/pentest_agent/docker_webctfagent.py
import asyncio
import uuid
import threading
import queue
import re
import subprocess
import contextvars
from typing import Type
from pydantic import BaseModel, Field

from src.core.database import SessionLocal
from src.core.models import AgentConfig
from src.tools.base import BaseSecurityTool
from src.tools.base import live_log_queue_var, event_loop_var,user_id_var

# [新增] 跨异步线程传递当前登录用户的 ID
webctf_user_id_var = contextvars.ContextVar('webctf_user_id_var', default=None)

class WebCTFAgentInput(BaseModel):
    target_url: str = Field(description="任务目标的 URL 或 IP 地址")
    task: str = Field(description="给 WebCTFAgent 的具体操作指令，如 '寻找后台漏洞并获取flag'")

class RunDockerWebCTFAgentTool(BaseSecurityTool):
    name: str = "RunDockeryyyAgent"
    description: str = "以隔离容器模式拉起 yyyagent 进行 Web CTF 打靶，安全分析和漏洞挖掘"
    args_schema: Type[BaseModel] = WebCTFAgentInput

    def _get_config(self):
        db = SessionLocal()
        try:
            user_id = user_id_var.get()
            
            # [修复 1] 确保查询的是 webctfagent，并且匹配当前登录的用户
            query = db.query(AgentConfig).filter(AgentConfig.agent_name == "webctfagent")
            if user_id:
                query = query.filter(AgentConfig.user_id == user_id)
            
            config = query.first()
            
            return {
                "api_key": config.api_key if config else "", 
                "model": config.model if config else "claude-opus-4-6"
            }
        except LookupError:
            return {"api_key": "", "model": "claude-opus-4-6"}
        finally:
            db.close()

    def _run(self, target_url: str, task: str) -> str:
        async_q = live_log_queue_var.get() if live_log_queue_var else None
        main_loop = event_loop_var.get() if event_loop_var else None
        
        log_queue = queue.Queue()
        cfg = self._get_config()
        
        api_key = "sk-X1VrCXlcBqjVDHKzRomSkDaEV112JS329EEXEGpiToNyOMBo"
        model_id ="claude-opus-4-6" 
        
        # 构建给 agent-test main.py 传递的环境变量
        docker_envs = [
            "-e", "PYTHONIOENCODING=utf-8",
            "-e", f"LLM_API_KEY={api_key}",
            "-e", f"LLM_MODEL_ID={model_id}",
            "-e", f"CTF_TARGET_URL=122.152.213.15:3000",
        ]

        # [修复 2] 动态适配 Base URL，防止官方 Key 请求到中转地址被报 401
        # 注意：如果你的 WebCTF Agent 必须全部走 OneAPI 中转，请直接解除下方第二行的注释，并填入你的中转地址！
        base_url = "https://tdyun.ai/"
        #if "deepseek" in model_id.lower(): base_url = "https://api.deepseek.com"
        #elif "qwen" in model_id.lower(): base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        #elif "gpt" in model_id.lower(): base_url = "https://api.openai.com/v1"
        
        # 如果需要强制走聚合中转站，请取消注释并修改下方地址：
        # base_url = "https://api.your-proxy-domain.com/v1"

        if base_url:
            docker_envs.extend(["-e", f"LLM_BASE_URL={base_url}"])

        def run_docker_subprocess():
            async def do_subprocess():
                container_name = f"webctf_{uuid.uuid4().hex[:8]}"
                log_queue.put(f"[LIVE] 🌐 准备拉起 yyyAgent 容器 [{container_name}] (模型: {model_id})")
                
                if not api_key:
                    log_queue.put(f"[LIVE] ❌ 认证拦截：未读取到 API Key，请先在前端配置！")
                    log_queue.put(None)
                    return
                
                try:
                    cmd = [
                        "docker", "run", "--rm",
                        "--name", container_name,
                        "-u", "root", 
                        "--privileged",
                        "--cpus=1.2",
                        "--memory=2048m",
                        "--memory-swap=2048m",
                    ]
                    cmd.extend(docker_envs)
                    
                    cmd.extend([
                        "yyy-agent:latest", 
                        "目标http://122.152.213.15:3000/","特别注意！获取基础信息后，先看你本地的知识库！本地知识库的内容可完全信任，牢记结束条件！",
                        task 
                    ])

                    process = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )

                    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGK]')
                    while True:
                        line = await process.stdout.readline()
                        if not line: break
                        clean_line = ansi_escape.sub('', line.decode('utf-8', errors='replace').strip())
                        if clean_line: log_queue.put(f"[LIVE] 🕵️ {clean_line}")

                    await process.wait()
                    log_queue.put(f"[LIVE] ✅ WebCTFAgent 任务结束，状态码: {process.returncode}")

                except Exception as e:
                    log_queue.put(f"[LIVE] 💥 [异常报错]: {str(e)}")
                    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
                finally:
                    log_queue.put(None)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(do_subprocess())
            loop.close()

        threading.Thread(target=run_docker_subprocess, daemon=True).start()
        
        full_logs = []
        while True:
            msg = log_queue.get()
            if msg is None: 
                break
                
            full_logs.append(msg)
            
            if async_q and main_loop:
                main_loop.call_soon_threadsafe(async_q.put_nowait, msg)
                
        return "\n".join(full_logs)
