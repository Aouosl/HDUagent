# src/tools/pentagi/service_tool.py
import asyncio
from typing import Type
from pydantic import BaseModel, Field
from src.tools.base import BaseSecurityTool, live_log_queue_var, event_loop_var, user_id_var
from src.core.database import SessionLocal
from src.core.models import AgentConfig
from .client import PentAGIClient

class PentAGIInput(BaseModel):
    task_description: str = Field(..., description="描述需要 PentAGI 执行的具体渗透测试任务、逆向分析目标或二进制漏洞挖掘需求。")

# 注意：这里改为继承 BaseSecurityTool
class PentAGIServiceTool(BaseSecurityTool):
    name: str = "GSAgent_analaze"
    description: str = "调用远程长效运行的 GSAgent 服务。适用于复杂的自动化渗透链路、深度二进制分析、逆向工程或持续性漏洞挖掘任务。"
    args_schema: Type[BaseModel] = PentAGIInput

    def _get_config(self):
        """从数据库读取当前用户的 pentagi 配置"""
        db = SessionLocal()
        try:
            user_id = user_id_var.get()
            query = db.query(AgentConfig).filter(AgentConfig.agent_name == "pentagi")
            if user_id:
                query = query.filter(AgentConfig.user_id == user_id)
            config = query.first()
            
            return {
                "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0aWQiOiJjbGVUcGdNT0ltIiwicmlkIjoxLCJ1aWQiOjEsInVoYXNoIjoiMjFjOTIzNjA1MWU3MTliYmVlNjY4ZGM0NjI3ZDcxOGYiLCJzdWIiOiJhcGlfdG9rZW4iLCJleHAiOjE3Nzc0Nzg0MDEsImlhdCI6MTc3NTM4OTcyOH0.vAp4EiVKnjSc9xtL-ZCsFhZIyBSTDa-BrBu20WJGz7o",
                # 注意：目前模型表里没有 url 字段，我们暂时约定如果前端输入模型，将默认取它，或你暂时写死
                "url": "https://118.31.239.206:8443" # <-- 请换成你实际的 PentAGI 地址
            }
        except LookupError:
            return {"api_key": "", "url": ""}
        finally:
            db.close()

    def _run(self, task_description: str) -> str:
        # 使用同步方法包裹异步逻辑
        async_q = live_log_queue_var.get() if live_log_queue_var else None
        main_loop = event_loop_var.get() if event_loop_var else None
        config = self._get_config()

        if not config.get("url") or not config.get("api_key"):
            return "错误：未配置 GSAgent 服务地址或 API Key。请在设置中完成配置。"

        def push_log(msg: str):
            if async_q and main_loop:
                main_loop.call_soon_threadsafe(async_q.put_nowait, f"[LIVE] {msg}")
            else:
                print(msg)

        async def run_pentagi_task():
            client = PentAGIClient(config['url'], config['api_key'])
            try:
                # --- 修改重点 ---
                # 在此指定你的 PentAGI 服务端配置生效的大模型 Provider
                # 如果你的 PentAGI 服务配置的是其他模型（比如 ollama），请改为 "ollama"
                model_provider = "custom" 
                
                push_log(f"🚀 正在连接远程 GSAgent 服务 (使用模型: {model_provider})")
                
                # 传入 provider，而不是原来的标题 "HDU-Agent Task"
                flow = await client.create_flow(model_provider, task_description)
                # --------------
                
                flow_id = flow['id']
                push_log(f"✅ 任务已创建，Flow ID: {flow_id}")

                last_status = None
                while True:
                    status_data = await client.get_flow_status(flow_id)
                    current_status = status_data['status']
                    
                    if current_status != last_status:
                        push_log(f"⏳ PentAGI 状态更新: {current_status}")
                        last_status = current_status

                    if current_status == 'finished':
                        push_log("🏁 PentAGI 任务已成功完成。")
                        return f"PentAGI 任务 {flow_id} 已执行完毕。建议登录 PentAGI 后台查看报告。"
                    
                    if current_status == 'failed':
                        push_log("❌ PentAGI 任务执行失败。")
                        return f"PentAGI 任务 {flow_id} 执行失败，请检查远程服务端日志。"

                    await asyncio.sleep(5)
            except Exception as e:
                push_log(f"💥 服务调用出错: {str(e)}")
                return f"PentAGI 服务调用出错: {str(e)}"

        # 阻塞执行异步协程
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_pentagi_task())
        loop.close()
        return result
