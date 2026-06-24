# src/Agent/subagent/recon_agent/graph.py
"""
Recon Agent graph assembly.

Builds a compiled LangGraph StateGraph with 5-node architecture.
Following the manager agent pattern with explicit routing.
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from .state import ReconPlan, ReconFinding, ReconReport, StepEvaluation
from .nodes import (
    make_orchestrator_node,
    make_worker_node,
    make_tools_node,
    make_evaluator_node,
    make_reporter_node,
    RECON_AGENT_SYSTEM_PROMPT,
)


# ==================== Graph Assembly ====================

def build_recon_agent() -> StateGraph:
    """Build the Recon Agent as a compiled LangGraph StateGraph.

    Internal graph structure:

        orchestrator --> worker <---> tools
                           |
                           v (no tool_calls)
                       evaluator
                        /  |  \
                  retry   continue   done
                    |       |         |
                    v       v         v
                  worker  worker   reporter --> END

    The compiled subgraph is added as a node in the parent manager graph.
    Communication via shared `messages` and `subagent_results` state keys.
    """
    from src.tools.registery import get_domain_tools

    agent_name = "recon_agent"

    # Get domain tools for recon
    tools = get_domain_tools(agent_name)

    # Create node functions
    orchestrator_fn = make_orchestrator_node(agent_name, RECON_AGENT_SYSTEM_PROMPT)
    worker_fn = make_worker_node(agent_name, RECON_AGENT_SYSTEM_PROMPT, tools)
    tools_fn = make_tools_node(tools)
    evaluator_fn = make_evaluator_node(agent_name)
    reporter_fn = make_reporter_node(agent_name)

    # Build graph with dict state (shares keys with parent AgentState)
    workflow = StateGraph(dict)

    workflow.add_node("orchestrator", orchestrator_fn)
    workflow.add_node("worker", worker_fn)
    workflow.add_node("tools", tools_fn)
    workflow.add_node("evaluator", evaluator_fn)
    workflow.add_node("reporter", reporter_fn)

    workflow.set_entry_point("orchestrator")
    workflow.add_edge("orchestrator", "worker")

    # Route after worker: has tool_calls -> tools, else -> evaluator
    def route_after_worker(state: dict) -> Literal["tools", "evaluator"]:
        messages = state.get("messages", [])
        if not messages:
            return "evaluator"
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
            return "tools"
        return "evaluator"

    workflow.add_conditional_edges("worker", route_after_worker, {
        "tools": "tools",
        "evaluator": "evaluator",
    })
    workflow.add_edge("tools", "worker")

    # Route after evaluator: retry/continue -> worker, done -> reporter
    def route_after_evaluator(state: dict) -> Literal["worker", "reporter"]:
        phase = state.get("sa_phase", "executing")
        if phase == "reporting":
            return "reporter"
        return "worker"

    workflow.add_conditional_edges("evaluator", route_after_evaluator, {
        "worker": "worker",
        "reporter": "reporter",
    })
    workflow.add_edge("reporter", END)

    compiled = workflow.compile()
    compiled.name = agent_name
    print(f"[{agent_name}] Graph compiled successfully (5 nodes: orchestrator->worker<->tools->evaluator->reporter)")
    return compiled
