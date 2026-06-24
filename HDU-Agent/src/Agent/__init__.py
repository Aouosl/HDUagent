# src/Agent/__init__.py
"""
HDU-Agent sub-agent module

Each sub-agent is a compiled LangGraph StateGraph with multi-node architecture:
  orchestrator -> worker <-> tools -> evaluator -> reporter

Sub-agents share the `messages` state with the parent manager graph.
Structured results are reported via `subagent_results` for manager consumption.

7 specialized sub-agents collaborate along the attack chain:
  recon -> web/code_audit/binary -> exploit -> internal -> report
"""
from src.Agent.subagent.web_agent import build_web_agent
from src.Agent.subagent.recon_agent import build_recon_agent
from src.Agent.subagent.exploit_agent import build_exploit_agent
from src.Agent.subagent.code_audit_agent import build_code_audit_agent
from src.Agent.subagent.binary_agent import build_binary_agent
from src.Agent.subagent.internal_agent import build_internal_agent
from src.Agent.subagent.report_agent import build_report_agent
from src.Agent.subagent.pentest_agent import build_pentest_agent

__all__ = [
    "build_recon_agent",
    "build_web_agent",
    "build_exploit_agent",
    "build_code_audit_agent",
    "build_binary_agent",
    "build_internal_agent",
    "build_report_agent",
    "build_pentest_agent",
]
