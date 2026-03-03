# src/Agent/manager/graph.py
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import manager_node, pentest_agent_node

# 1. 初始化图状态
workflow = StateGraph(AgentState)

# 2. 添加所有节点（Manager和子智能体都要在这里注册）
workflow.add_node("manager", manager_node)
workflow.add_node("pentest_agent", pentest_agent_node)

# 3. 设置图的起点
workflow.set_entry_point("manager")

# 4. 定义条件路由函数 (已修复)
def route_after_manager(state: AgentState) -> str:
    """根据 manager_node 的决策返回对应的路由键"""
    # 这里的返回值必须是下面字典中的键
    target = state.get("next_node", "FINISH")
    return target

# 5. 添加条件边
workflow.add_conditional_edges(
    "manager",
    route_after_manager,
    {
        "FINISH": END,                   # 当路由函数返回 "FINISH" 时，图真正走向结束
        "pentest_agent": "pentest_agent" # 当返回 "pentest_agent" 时，去调用子节点
    }
)

# 6. 子智能体执行完后，无条件回到 manager 节点评估结果
workflow.add_edge("pentest_agent", "manager")

# 7. 编译图
app = workflow.compile()