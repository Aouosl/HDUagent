# src/Agent/manager/state.py
from typing import Annotated, TypedDict, Optional, Any, Dict
from langgraph.graph.message import add_messages
from src.Agent.subagent.protocol import AgentTaskRequest, AgentTaskResponse


class AgentState(TypedDict):
    # 保存对话消息列表
    messages: Annotated[list, add_messages]

    # --- 新增：用于多智能体路由的控制字段 ---
    next_node: Optional[str]  # Manager 决定的下一个子智能体名称
    current_task: Optional[AgentTaskRequest]  # Manager 下发给子智能体的具体任务书
    last_response: Optional[AgentTaskResponse]  # 子智能体执行完毕后返回的汇报结果