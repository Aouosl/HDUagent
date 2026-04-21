# src/Agent/manager/nodes.py
from typing import Optional
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from .state import AgentState
from src.core.llm_factory import get_llm
from src.tools.registery import get_all_tools  # 引入工具注册表
from src.config.settings import settings 
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from src.core.database import SessionLocal
from src.core.models import User, AgentExperience  # 如果你的模型在 models.py 里
def get_dynamic_agent_experiences() -> str:
    """从数据库获取 Manager 积累的子智能体经验"""
    db: Session = SessionLocal()
    try:
        experiences = db.query(AgentExperience).all()
        if not experiences:
            return "目前还没有积累使用经验，请根据各个工具的默认描述进行调用。"
        
        exp_texts = []
        for exp in experiences:
            exp_texts.append(f"- 【{exp.agent_name}】: 胜率(成功{exp.success_count}/失败{exp.fail_count})。\n  经验总结：{exp.learned_expertise}")
        return "\n".join(exp_texts)
    finally:
        db.close()
# --- 1. 更新 Schema，增加 intent_tags ---
class TaskBreakdown(BaseModel):
    is_complex: bool = Field(description="该用户输入是否为一个需要拆解的复杂任务。普通问答请返回 False。")
    analysis: str = Field(description="对用户意图的深度理解和测试策略分析")
    steps: list[str] = Field(description="拆解出的具体执行步骤列表（如不需要拆解，可为空列表）")
    # [新增] 自动提取画像标签
    intent_tags: list[str] = Field(default_factory=list, description="从用户输入中提取的技能领域或关注点标签（如: web, sql注入, pwn, 提权等），最多提取3个核心词")

# --- [新增] 画像自动落库辅助函数 ---
def auto_update_portrait_tags(user_id: int, new_tags: list):
    if not user_id or not new_tags:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            portrait = user.portrait_data or {}
            existing_tags = portrait.get("interest_tags", [])
            
            # 合并并去重，同时限制最多保留最近的 15 个标签（防上下文爆炸）
            updated_tags = list(dict.fromkeys(existing_tags + new_tags))[-15:]
            portrait["interest_tags"] = updated_tags
            
            # 顺便提升一点活跃度
            portrait["activity_score"] = portrait.get("activity_score", 0) + 1
            
            user.portrait_data = portrait
            flag_modified(user, "portrait_data")
            db.commit()
    except Exception as e:
        print(f"⚠️ 更新用户画像失败: {e}")
    finally:
        db.close()

# --- 2. 修改 analyzer_node ---
def analyzer_node(state: AgentState):
    """意图拆解节点：在执行任务前，先拆分为多个可执行步骤，并提取画像标签"""
    messages = state.get('messages', [])
    if not messages: return {}
    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage): return {}

    current_provider = state.get("current_provider") or settings.DEFAULT_PROVIDER
    current_model = state.get("current_model") or settings.DEFAULT_MODEL
    user_key = state.get('user_api_keys', {}).get(current_provider)
    
    llm = get_llm(provider=current_provider, model_name=current_model, api_key=user_key)
    structured_llm = llm.with_structured_output(TaskBreakdown)

    prompt = SystemMessage(content=(
        "你是一个高级网络安全架构师。分析用户的最新输入。"
        "1. 如果是复杂任务，请拆解为步骤 (is_complex=True)。"
        "2. 无论是否复杂，请提取用户当前关注的技术领域或知识点标签填入 intent_tags。"
    ))

    try:
        result = structured_llm.invoke([prompt, last_message])
        
        # [新增] 异步/后台更新用户画像（利用刚刚写好的辅助函数）
        if result.intent_tags and state.get("user_id"):
            print(f"🏷️ [Analyzer] 捕获到用户特征标签: {result.intent_tags}")
            auto_update_portrait_tags(state["user_id"], result.intent_tags)

        if result.is_complex and result.steps:
            # ... 保持原有的拆解拼装代码 ...
            plan_text = f"**💡 意图理解与任务拆解**\n\n**分析:** {result.analysis}\n\n**执行计划:**\n"
            for i, step in enumerate(result.steps): plan_text += f"{i+1}. {step}\n"
            return {"intent_analysis": result.analysis, "task_plan": result.steps, "messages": [AIMessage(content=plan_text)]}
        else:
            return {"task_plan": []} 
    except Exception as e:
        return {}


def get_user_portrait_context(user_id: int) -> str:
    """从数据库获取当前用户的画像并转化为自然语言上下文"""
    if not user_id:
        return ""
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.portrait_data:
            return ""
        
        p_data = user.portrait_data
        tech_stack = ", ".join(p_data.get("tech_stack", [])) or "未知"
        interest_tags = ", ".join(p_data.get("interest_tags", [])) or "无"
        risk_level = p_data.get("risk_level", "low")
        
        return (
            "=====================\n"
            "【当前交互用户的画像与偏好】\n"
            f"- 擅长领域/技术栈: {tech_stack}\n"
            f"- 近期兴趣/意图标签: {interest_tags}\n"
            f"- 账号风控等级: {risk_level}\n"
            "-> 请结合该用户的画像调整你的沟通策略：对于其擅长的领域可直接深入原理或执行高级测试；若涉及其不熟悉的领域标签，请在结果中补充基础科普。\n"
            "=====================\n"
        )
    except Exception as e:
        print(f"⚠️ 获取用户画像上下文失败: {e}")
        return ""
    finally:
        db.close()


# --- 3. 完整修改后的 manager_node ---
def manager_node(state: AgentState):
    """主智能体节点：处理失败回退询问逻辑"""
    messages = state['messages']
    user_api_keys = state.get('user_api_keys', {})
    
    current_provider = state.get("current_provider") or settings.DEFAULT_PROVIDER
    current_model = state.get("current_model") or settings.DEFAULT_MODEL
    user_key = user_api_keys.get(current_provider)
    
    llm = get_llm(provider=current_provider, model_name=current_model, api_key=user_key)

    # --- 获取各种上下文（经验、画像、计划）---
    history_experience = get_dynamic_agent_experiences()
    portrait_context = get_user_portrait_context(state.get("user_id"))

    task_plan = state.get("task_plan")
    plan_context = ""
    if task_plan:
        plan_context = "\n=====================\n【全局任务拆解计划】\n"
        for i, step in enumerate(task_plan):
            plan_context += f"{i+1}. {step}\n"
        plan_context += "-> 请严格参考以上计划评估当前进度，并调用对应的工具推进下一步。\n=====================\n"

    # --- [新增] 处理工具失败逻辑 ---
    last_tool_status = state.get("last_tool_status")
    force_ask_user = (last_tool_status == "failure")

    # 基础 System Prompt
    system_prompt_content = (
        "你是自动化安全测试系统 HDU-Agent 的主控智能体（Manager）。\n"
        "你的任务是理解用户意图，并准确地将任务分发给最合适的子智能体（工具）。\n\n"
        f"{portrait_context}"
        f"{plan_context}"
        "=====================\n"
        "【你的长期记忆：各子智能体特长总结】\n"
        f"{history_experience}\n"
        "=====================\n\n"
        "【你的行为准则】\n"
        "1. 分发任务：请严格参考上述经验记忆和【全局任务拆解计划】，选择最合适的工具去执行。\n"
        "2. 沟通语气：务必参考【当前交互用户的画像与偏好】调整回复风格。\n"
        "3. 直接对话：如果任务已完成，或者只是回答用户的普通问题，请直接用自然语言回复。"
    )

    # [新增] 如果上一步工具执行失败，追加特殊指令
    if force_ask_user:
        system_prompt_content += (
            "\n\n【!!! 重要 !!!】\n"
            "你上一次调用的工具执行失败了。"
            "此时你**绝对不能**自动选择另一个工具。"
            "请用自然语言向用户报告失败情况，并明确询问用户下一步意图（例如：是否重试？是否换用其他方法？或是否终止任务？）。"
        )
        # 失败时不绑定工具，强制 LLM 只能文本回复
        llm_to_use = llm
    else:
        # 正常情况绑定所有工具
        llm_to_use = llm.bind_tools(get_all_tools())

    system_prompt = SystemMessage(content=system_prompt_content)
    
    print(f"🧠 [Manager] 正在思考 (引擎: {current_provider} / {current_model})...")
    if force_ask_user:
        print("⚠️ [Manager] 检测到上一次工具执行失败，已限制工具调用，将要求 LLM 询问用户。")

    response = llm_to_use.invoke([system_prompt] + messages)

    # 返回时清除状态（避免影响下一次正常流程）
    return {
        "messages": [response],
        "last_tool_status": None   # 重置状态，下次调用前为 None
    }

def pentest_agent_node(state: AgentState):
    """工具执行节点：执行 Tool Call 并标记执行状态"""
    last_message = state['messages'][-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {
            "messages": [SystemMessage(content="错误：未检测到合法的工具调用指令。")],
            "last_tool_status": "failure"   # 未调用工具也视为失败
        }

    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    tools = {t.name: t for t in get_all_tools()}
    selected_tool = tools.get(tool_name)

    if not selected_tool:
        result_message = f"错误：找不到名为 {tool_name} 的工具。"
        status = "failure"
    else:
        print(f"🔧 [Tool Executor] 正在执行工具 {tool_name}，参数: {tool_args}")
        try:
            result_message = selected_tool.invoke(tool_args)
            # 判断结果是否包含失败关键词（可根据实际返回结构调整）
            if any(keyword in str(result_message).lower() for keyword in ["失败", "错误", "error", "failed"]):
                status = "failure"
            else:
                status = "success"
        except Exception as e:
            result_message = f"工具执行时发生异常：{str(e)}"
            status = "failure"

    tool_msg = ToolMessage(
        content=str(result_message),
        tool_call_id=tool_call_id,
        name=tool_name
    )

    return {
        "messages": [tool_msg],
        "last_tool_status": status   # 传递状态
    }

async def analyze_user_intent(state: AgentState):
    """
    专门负责分析用户意图并生成标签的节点
    """
    llm = get_llm() # 获取当前配置的 LLM
    
    # 构造意图识别的 Prompt
    intent_prompt = """
    你是一个安全专家助手。请分析用户的最新输入，并输出对应的意图标签（JSON格式）。
    可选标签体系：
    - 领域: web, pwn, reverse, crypto, mobile, misc
    - 行为: scan, exploit, audit, learn, troubleshoot
    - 风险: low, medium, high
    
    输出示例: {"tags": ["web", "scan"], "risk": "low", "summary": "用户想要扫描Web目标"}
    """
    
    last_message = state["messages"][-1].content
    response = await llm.ainvoke([
        {"role": "system", "content": intent_prompt},
        {"role": "user", "content": last_message}
    ])
    
    # 将分析结果存入 state
    return {"intent_analysis": response.content}
