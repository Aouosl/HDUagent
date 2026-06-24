# src/Agent/subagent/__init__.py
"""
LangGraph 子智能体模块

每个子智能体是一个编译好的 LangGraph StateGraph，
通过共享 `messages` 状态与父图（manager）通信。

所有子智能体统一使用 manager/subagent_factory.py 的 5 节点工厂：
    orchestrator -> worker <-> tools -> evaluator -> reporter

要创建新的子智能体，请在本目录下创建 <name>_agent/ 子包，
参考 recon_agent/ 或使用工厂函数单文件模式。
"""
from .base import create_domain_subgraph

__all__ = ["create_domain_subgraph"]
