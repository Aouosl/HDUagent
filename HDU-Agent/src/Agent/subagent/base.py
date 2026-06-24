# src/Agent/subagent/base.py
"""
子智能体工厂 — 委托到统一的 5 节点工厂。

原本此文件包含一个简单的 2 节点 ReAct 实现（agent ⇄ tools）。
现已统一为由 src.Agent.manager.subagent_factory 提供的
5 节点架构（orchestrator → worker ⇄ tools → evaluator → reporter）。

保留此文件仅为向后兼容（如果外部有引用）。
"""
from typing import List, Optional, Callable
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph


def create_domain_subgraph(
    agent_name: str,
    system_prompt: str,
    tools: Optional[List[BaseTool]] = None,
    max_iterations: int = 5,
    max_retries: int = 2,
) -> StateGraph:
    """
    创建一个领域专用的 LangGraph 子智能体。

    委托到统一的 5 节点工厂实现（orchestrator → worker ⇄ tools → evaluator → reporter）。

    Args:
        agent_name: 子智能体名称（用于日志和路由）
        system_prompt: 领域专用的 system prompt
        tools: 该子智能体绑定的工具列表（None 则使用全部通用工具）
        max_iterations: 最大 ReAct 迭代次数，防止死循环
        max_retries: 单步最大重试次数

    Returns:
        编译好的 StateGraph 子图
    """
    from src.Agent.manager.subagent_factory import create_domain_subgraph as _factory_create
    return _factory_create(
        agent_name=agent_name,
        system_prompt=system_prompt,
        tools=tools,
        max_iterations=max_iterations,
        max_retries=max_retries,
    )
