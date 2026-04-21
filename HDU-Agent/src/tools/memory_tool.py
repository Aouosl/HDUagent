# src/tools/memory_tool.py
from typing import Type # 新增导入 Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from src.core.database import SessionLocal
from src.core.models import AgentExperience

class UpdateMemoryArgs(BaseModel):
    agent_name: str = Field(..., description="要更新经验的子智能体名称")
    new_expertise_summary: str = Field(..., description="基于近期对话，对该智能体能力的新总结。请保留旧有长处，加入新发现。")
    is_success: bool = Field(..., description="这次调度是否成功解决了用户问题？")

class UpdateAgentMemoryTool(BaseTool):
    # 下面这三行加上类型注解
    name: str = "update_agent_memory"
    description: str = "当用户评价某个智能体的工作，或者你发现某个智能体擅长/不擅长某类任务时，调用此工具更新经验记忆库。"
    args_schema: Type[BaseModel] = UpdateMemoryArgs

    def _run(self, agent_name: str, new_expertise_summary: str, is_success: bool):
        db = SessionLocal()
        try:
            exp = db.query(AgentExperience).filter(AgentExperience.agent_name == agent_name).first()
            if not exp:
                exp = AgentExperience(agent_name=agent_name)
                db.add(exp)
            
            # 更新经验描述和统计
            exp.learned_expertise = new_expertise_summary
            if is_success:
                exp.success_count += 1
            else:
                exp.fail_count += 1
                
            db.commit()
            return f"✅ 成功更新了关于 {agent_name} 的经验记忆！"
        finally:
            db.close()
