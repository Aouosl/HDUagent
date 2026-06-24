# src/tools/registery.py
"""
工具注册表 - 保留通用工具注册，领域专属工具由 tool_registry 管理
"""
from typing import List
from langchain_core.tools import BaseTool
from src.tools.memory_tool import UpdateAgentMemoryTool


def get_all_tools() -> List[BaseTool]:
    """返回所有已注册的通用工具"""
    return [
        UpdateAgentMemoryTool(),
    ]


def get_tool_by_name(name: str) -> BaseTool | None:
    """按名称查找工具"""
    tools = {t.name: t for t in get_all_tools()}
    return tools.get(name)


def get_domain_tools(agent_name: str) -> List[BaseTool]:
    """
    获取指定子智能体的专属工具列表。
    委托给 tool_registry 进行领域工具映射。

    Args:
        agent_name: 子智能体名称（如 "recon_agent"）

    Returns:
        工具实例列表
    """
    from src.tools.tool_registry import get_tools_for_agent
    return get_tools_for_agent(agent_name)
