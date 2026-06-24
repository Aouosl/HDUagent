# src/Agent/manager/graph.py
"""
HDU-Agent Main Graph: orchestrator -> manager -> sub-agent dispatch

Architecture:
    analyzer (intent decomposition)
        |
    manager (dispatch decision)
      /    |    |    |    |    |    \\
 recon  web exploit code_audit binary internal report
      \\    |    |    |    |    |    /
        manager (result check, continue/finish)

Each sub-agent is a compiled LangGraph StateGraph with:
  orchestrator -> worker <-> tools -> evaluator -> reporter
Sub-agents communicate with the manager through shared `messages`
and structured `subagent_results`.
"""
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import manager_node, analyzer_node
from src.Agent import (
    build_web_agent,
    build_recon_agent,
    build_exploit_agent,
    build_code_audit_agent,
    build_binary_agent,
    build_internal_agent,
    build_report_agent,
    build_pentest_agent,
)

# ==================== Build Sub-Agents (compiled subgraphs) ====================
recon_subgraph = build_recon_agent()
web_subgraph = build_web_agent()
exploit_subgraph = build_exploit_agent()
code_audit_subgraph = build_code_audit_agent()
binary_subgraph = build_binary_agent()
internal_subgraph = build_internal_agent()
report_subgraph = build_report_agent()
pentest_subgraph = build_pentest_agent()

# ==================== Build Main Graph ====================
workflow = StateGraph(AgentState)

# 1. Register nodes
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("manager", manager_node)
workflow.add_node("recon_agent", recon_subgraph)
workflow.add_node("web_agent", web_subgraph)
workflow.add_node("exploit_agent", exploit_subgraph)
workflow.add_node("code_audit_agent", code_audit_subgraph)
workflow.add_node("binary_agent", binary_subgraph)
workflow.add_node("internal_agent", internal_subgraph)
workflow.add_node("report_agent", report_subgraph)
workflow.add_node("pentest_agent", pentest_subgraph)

# 2. Entry point: analyzer
workflow.set_entry_point("analyzer")
workflow.add_edge("analyzer", "manager")

# 3. Conditional routing after manager
def route_after_manager(state: AgentState) -> str:
    """Route after manager decides dispatch target.

    - subagent_dispatch is set -> enter specified sub-agent
    - subagent_dispatch is empty -> manager replied directly, end conversation
    """
    dispatch = state.get("subagent_dispatch", "")

    valid_agents = {
        "recon_agent", "web_agent", "exploit_agent",
        "code_audit_agent", "binary_agent",
        "internal_agent", "report_agent", "pentest_agent",
    }

    if dispatch in valid_agents:
        print(f"[Router] Manager dispatch -> {dispatch}")
        return dispatch
    else:
        if dispatch:
            print(f"[Router] Unknown dispatch target '{dispatch}', ending")
        else:
            print("[Router] Manager direct reply, conversation end")
        return "FINISH"

workflow.add_conditional_edges(
    "manager",
    route_after_manager,
    {
        "FINISH": END,
        "recon_agent": "recon_agent",
        "web_agent": "web_agent",
        "exploit_agent": "exploit_agent",
        "code_audit_agent": "code_audit_agent",
        "binary_agent": "binary_agent",
        "internal_agent": "internal_agent",
        "report_agent": "report_agent",
        "pentest_agent": "pentest_agent",
    }
)

# 4. After sub-agent completes, return to manager for result evaluation
workflow.add_edge("recon_agent", "manager")
workflow.add_edge("web_agent", "manager")
workflow.add_edge("exploit_agent", "manager")
workflow.add_edge("code_audit_agent", "manager")
workflow.add_edge("binary_agent", "manager")
workflow.add_edge("internal_agent", "manager")
workflow.add_edge("report_agent", "manager")
workflow.add_edge("pentest_agent", "manager")

# 5. Compile
app = workflow.compile()
