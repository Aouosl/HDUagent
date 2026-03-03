# src/tools/registry.py
from typing import List
from langchain_core.tools import BaseTool
# 导入你写好的工具
'''
from src.tools.scanners.fscan_tool import FscanTool

def get_all_tools() -> List[BaseTool]:
    """
    集中返回所有已注册的工具。
    大模型（Manager Agent）将通过此函数获取其可以使用的所有能力。
    """
    return [
        FscanTool(),
        # 后续只需在这里继续添加：
        # SqlmapTool(),
        # DirsearchTool(),
        # PentestAGITool(),
    ]
'''