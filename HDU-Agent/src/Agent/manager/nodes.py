# src/Agent/manager/nodes.py
from typing import Optional
import json
import re
from .state import AgentState
from src.core.llm_factory import get_llm
from src.Agent.subagent.protocol import AgentTaskRequest

llm = get_llm()


def extract_json_from_text(text: str) -> dict:
    """从大模型的文本回复中安全提取 JSON"""
    # 1. 尝试匹配 markdown 的 json 代码块
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass

    # 2. 如果没有代码块，尝试直接寻找大括号包裹的内容
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
    except:
        pass

    raise ValueError("无法从模型输出中提取合法的 JSON 结构。")


def manager_node(state: AgentState):
    """主智能体节点：理解意图，生成路由决策（兼容不支持 Structured Output 的模型）"""
    messages = state['messages']

    # 将 JSON Schema 约束直接写在提示词里
    system_prompt = {
        "role": "system",
        "content": (
            "你是自动化安全测试系统的主控智能体。你的任务是理解用户意图，并将其拆解为具体任务分发给子智能体。\n"
            "目前可用的子智能体:\n"
            "- pentest_agent: 负责资产信息收集、扫描和命令执行。\n\n"
            "【输出格式要求】\n"
            "你必须且只能输出一个合法的 JSON 对象，不要包含任何多余的解释性文字。JSON 结构如下：\n"
            "{\n"
            '  "intent_analysis": "对用户指令的思考和意图分析",\n'
            '  "next_node": "选择要调用的子智能体(如 pentest_agent)。如果任务已完成或不需要调用，填 FINISH",\n'
            '  "task_request": {\n'
            '       "task_id": "任务唯一标识(如 task_001)",\n'
            '       "target": "任务目标(如 IP地址、域名)",\n'
            '       "intent": "给子智能体的具体操作指令",\n'
            '       "context_data": {}\n'
            '  }, // 如果 next_node 是 FINISH，此项设为 null\n'
            '  "reply_to_user": "直接回复给用户的自然语言话术"\n'
            "}"
        )
    }

    print("🧠 [Manager] 正在思考和决策...")
    # 直接调用普通 invoke，不使用 with_structured_output
    response = llm.invoke([system_prompt] + messages)
    response_text = response.content

    try:
        # 手动解析 JSON
        decision_dict = extract_json_from_text(response_text)

        next_node = decision_dict.get("next_node", "FINISH")
        reply_to_user = decision_dict.get("reply_to_user", "好的，我已了解。")
        task_data = decision_dict.get("task_request")

        # 组装任务书
        current_task = None
        if next_node != "FINISH" and task_data:
            current_task = AgentTaskRequest(**task_data)

    except Exception as e:
        # 容错降级机制：如果模型没按要求输出 JSON
        print(f"⚠️ [Manager] 解析模型输出失败: {e}\n模型原始输出:\n{response_text}")
        next_node = "FINISH"
        reply_to_user = f"抱歉，我理解了你的话，但在生成任务下发结构时出现了格式错误。"
        current_task = None

    # 更新全局状态
    return {
        "messages": [("assistant", reply_to_user)],
        "next_node": next_node,
        "current_task": current_task
    }


# src/Agent/manager/nodes.py 追加内容
from src.Agent.subagent.pentest_wrapper import PentestAgentWrapper


def pentest_agent_node(state: AgentState):
    """LangGraph 调用的节点函数：触发 pentest-agent 包装器"""
    current_task = state.get("current_task")

    if not current_task:
        # 异常兜底：如果没有任务书，直接返回
        return {"messages": [("assistant", "错误：未收到有效任务书。")]}

    # 实例化我们的包装器并执行任务
    wrapper = PentestAgentWrapper()
    response = wrapper.execute_task(current_task)

    # 生成一条系统消息告知 Manager 执行结果
    result_message = (
        f"子智能体执行汇报:\n"
        f"状态: {response.status}\n"
        f"摘要: {response.summary}\n"
        f"错误: {response.error_msg if response.error_msg else '无'}"
    )

    # 更新全局状态：追加消息，并保存 last_response 供 Manager 评估
    return {
        "messages": [("user", result_message)],  # 伪装成 user 输入，逼迫 manager 进行总结或下发新任务
        "last_response": response,
        # 执行完毕后，状态流转控制权交回给 Manager 进行下一步决策
        "next_node": "manager"
    }