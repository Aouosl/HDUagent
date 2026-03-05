# src/Agent/manager/state.py
from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages



class AgentState(TypedDict):
    # 保存对话消息列表，大模型的 AIMessage 和工具的 ToolMessage 都会自动追加到这里
    messages: Annotated[list, add_messages]
