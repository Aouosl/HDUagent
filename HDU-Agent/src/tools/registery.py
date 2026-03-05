# src/tools/registry.py
from typing import List
from langchain_core.tools import BaseTool
# 导入你写好的工具

from typing import List
from langchain_core.tools import BaseTool
from src.tools.pentest_agent.pentest_tool import PentestAgentTool

def get_all_tools() -> List[BaseTool]:
    """集中返回所有已注册的工具。"""
    return [
        PentestAgentTool(),
        # 后续其他工具...
    ]