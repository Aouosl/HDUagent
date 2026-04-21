# src/tools/registry.py
from typing import List
from langchain_core.tools import BaseTool
# 导入你写好的工具
from src.tools.pentestagent.docker_security_analyzer import RunDockerSecurityAnalysisTool
from typing import List
from langchain_core.tools import BaseTool
from src.tools.pentest_agent.docker_pentestagent import RunDockerContainerPentestTool
from src.tools.ctf_agent.ctf_agent_tool import RunDockerWebCTFAgentTool
from src.tools.pentagi.service_tool import PentAGIServiceTool
from src.tools.memory_tool import UpdateAgentMemoryTool
def get_all_tools() -> List[BaseTool]:
    """集中返回所有已注册的工具。"""
    return [
        RunDockerContainerPentestTool(),
        RunDockerWebCTFAgentTool(),
        PentAGIServiceTool(),
        UpdateAgentMemoryTool(),
        RunDockerSecurityAnalysisTool(),
        # 后续其他工具...

    ]
