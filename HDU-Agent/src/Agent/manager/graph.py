# src/Agent/manager/graph.py
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import manager_node, pentest_agent_node, analyzer_node # 新增导入 analyzer_node
from langchain_core.messages import AIMessage

workflow = StateGraph(AgentState)

# 1. 注册所有的 Node
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("manager", manager_node)
workflow.add_node("pentest_agent", pentest_agent_node)

# 2. 将图的起点设置为 analyzer
workflow.set_entry_point("analyzer")

# 3. 添加从 analyzer 流向 manager 的必经边
workflow.add_edge("analyzer", "manager")

# 核心路由逻辑保持不变
def route_after_manager(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "FINISH"

    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "pentest_agent"

    return "FINISH"

workflow.add_conditional_edges(
    "manager",
    route_after_manager,
    {
        "FINISH": END,
        "pentest_agent": "pentest_agent"
    }
)

# 工具执行完毕后，回流 manager 检查结果并进行下一步
workflow.add_edge("pentest_agent", "manager")

app = workflow.compile()
