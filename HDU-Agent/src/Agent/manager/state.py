# src/Agent/manager/state.py
from typing import Annotated, TypedDict, Optional, List
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_api_keys: dict
    user_id: Optional[int]
    current_provider: Optional[str]
    current_model: Optional[str]
    intent_analysis: Optional[str]
    task_plan: Optional[List[str]]
    
    # [新增] 上一次工具调用的执行状态
    last_tool_status: Optional[str]   # "success" 或 "failure"
