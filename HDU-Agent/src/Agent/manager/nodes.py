# src/Agent/manager/nodes.py
from typing import Optional
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from .state import AgentState
from src.core.llm_factory import get_llm
from src.tools.registery import get_all_tools  # 引入工具注册表

llm = get_llm()


def manager_node(state: AgentState):
    """主智能体节点：基于 Tool Calling 范式进行决策"""
    messages = state['messages']

    system_prompt = SystemMessage(content=(
        "你是自动化安全测试系统的主控智能体。\n"
        "你的任务是理解用户意图。如果需要执行实际的扫描和测试任务，请调用合适的工具（如 CallPentestAgent）。\n"
        "如果任务已完成，或者只是回答用户的普通问题，请直接用自然语言回复。\n\n"
        "【安全测试规范】\n"
        "在进行端口扫描时，严禁使用 -p-，请优先使用 --top-ports 1000 或 -F 快速扫描，配合 -T4 提升速度。"
    ))

    print("🧠 [Manager] 正在思考和决策...")

    # 核心修改：动态从注册表获取所有工具，并绑定到大模型
    tools = get_all_tools()
    llm_with_tools = llm.bind_tools(tools)

    response = llm_with_tools.invoke([system_prompt] + messages)
    return {"messages": [response]}


def pentest_agent_node(state: AgentState):
    """工具执行节点（重构后）：接收 Tool Call 并动态路由到对应的 Tool 类执行"""
    last_message = state['messages'][-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": [SystemMessage(content="错误：未检测到合法的工具调用指令。")]}

    # 获取大模型想要调用的工具和参数
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    # 从注册表中找到对应的工具并执行
    tools = {t.name: t for t in get_all_tools()}
    selected_tool = tools.get(tool_name)

    if not selected_tool:
        result_message = f"错误：找不到名为 {tool_name} 的工具。"
    else:
        print(f"🔧 [Tool Executor] 正在执行工具 {tool_name}，参数: {tool_args}")
        # 执行刚才写的 PentestAgentTool 的 _run 方法 (即发送 HTTP 请求)
        result_message = selected_tool.invoke(tool_args)

    # 生成标准的 ToolMessage 返回给大模型
    tool_msg = ToolMessage(
        content=str(result_message),
        tool_call_id=tool_call_id,
        name=tool_name
    )

    return {
        "messages": [tool_msg]
    }