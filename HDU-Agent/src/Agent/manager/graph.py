# src/Agent/manager/graph.py
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import manager_node, pentest_agent_node
from langchain_core.messages import AIMessage

workflow = StateGraph(AgentState)

workflow.add_node("manager", manager_node)
workflow.add_node("pentest_agent", pentest_agent_node)

workflow.set_entry_point("manager")


# 核心路由逻辑：判断最后一条消息是否包含工具调用
def route_after_manager(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "FINISH"

    last_message = messages[-1]

    # 如果大模型决定调用工具，它会返回带有 tool_calls 属性的 AIMessage
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "pentest_agent"

    # 如果没有 tool_calls，说明大模型直接用自然语言回复了用户，流程结束
    return "FINISH"


workflow.add_conditional_edges(
    "manager",
    route_after_manager,
    {
        "FINISH": END,
        "pentest_agent": "pentest_agent"
    }
)

# 子智能体返回 ToolMessage 后，无条件流转回 manager，让 manager 看结果并做总结
workflow.add_edge("pentest_agent", "manager")

app = workflow.compile()