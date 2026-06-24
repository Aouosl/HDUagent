# src/Agent/manager/nodes.py
"""
HDU-Agent 核心节点

- analyzer_node: 意图拆解 + 标签提取
- manager_node: 决策调度（决定分派给哪个子智能体或直接回复）
"""
from typing import Optional, List, Dict, Any
from langchain_core.messages import (
    SystemMessage, ToolMessage, AIMessage, HumanMessage, trim_messages
)
from .state import AgentState
from src.core.llm_factory import get_llm
from src.config.settings import settings
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from src.core.database import SessionLocal
from src.core.models import User, AgentExperience


# ==================== 工具函数 ====================

def get_dynamic_agent_experiences() -> str:
    """从数据库获取累积的子智能体经验"""
    db: Session = SessionLocal()
    try:
        experiences = db.query(AgentExperience).all()
        if not experiences:
            return "目前还没有累积使用经验，请根据需求合理调度子智能体。"
        exp_texts = []
        for exp in experiences:
            exp_texts.append(
                f"- 【{exp.agent_name}】成功率(成功{exp.success_count}/失败{exp.fail_count})。\n"
                f"  经验总结：{exp.learned_expertise}"
            )
        return "\n".join(exp_texts)
    finally:
        db.close()


def get_user_portrait_text(user_id: Optional[int]) -> str:
    """获取用户画像文本"""
    if not user_id:
        return ""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.portrait_data:
            return ""
        portrait = user.portrait_data
        parts = []
        if portrait.get("interest_tags"):
            parts.append(f"- 关注领域：{', '.join(portrait['interest_tags'])}")
        if portrait.get("skill_level"):
            parts.append(f"- 技能水平：{portrait['skill_level']}")
        return "\n".join(parts) if parts else ""
    finally:
        db.close()


# ==================== Analyzer 节点 Schema ====================

class TaskBreakdown(BaseModel):
    is_complex: bool = Field(description="该用户输入是否为一个需要拆解的复杂任务。")
    analysis: str = Field(description="对用户意图的深度理解和策略分析")
    steps: list[str] = Field(description="拆解出的具体执行步骤列表")
    intent_tags: list[str] = Field(default_factory=list, description="技能领域标签（web/pwn/pentest/ctf等），最多3个")


def auto_update_portrait_tags(user_id: int, new_tags: list):
    if not user_id or not new_tags:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            portrait = user.portrait_data or {}
            existing_tags = portrait.get("interest_tags", [])
            updated_tags = list(dict.fromkeys(existing_tags + new_tags))[-15:]
            portrait["interest_tags"] = updated_tags
            portrait["activity_score"] = portrait.get("activity_score", 0) + 1
            user.portrait_data = portrait
            flag_modified(user, "portrait_data")
            db.commit()
    except Exception as e:
        print(f"\u26a0\ufe0f 更新用户画像失败: {e}")
    finally:
        db.close()


# ==================== Manager 调度决策 Schema ====================

class DispatchDecision(BaseModel):
    """Manager 的结构化调度决策"""
    situation_analysis: str = Field(description="对当前执行上下文的分析：用户意图、当前进展、上一步结果")
    dispatch_target: Optional[str] = Field(
        default=None,
        description="调度的子智能体名称：'recon_agent' / 'web_agent' / 'exploit_agent' / 'code_audit_agent' / 'binary_agent' / 'internal_agent' / 'report_agent'。不需要调度时为 null"
    )
    task_instruction: str = Field(
        default="",
        description="给子智能体的具体任务指令（清晰描述目标、范围、期望输出）"
    )
    reasoning: str = Field(description="为什么选择这个子智能体（或不调度）的推理过程")
    is_task_complete: bool = Field(description="任务是否已完成，无需进一步行动")


# ==================== 子智能体选择指南 ====================

SUBAGENT_SELECTION_GUIDE = """
## 可用子智能体及适用场景

### recon_agent（信息收集子智能体）
- 适用：端口扫描、服务枚举、DNS侦察、子域名发现、OS指纹识别、资产清单
- 不适用：漏洞利用、代码分析、Web漏洞扫描
- 典型作为攻击链第一阶段

### web_agent（Web安全子智能体）
- 适用：Web漏洞扫描（SQL注入/XSS/CSRF/SSRF等）、Web指纹识别、API安全测试、Web配置审计
- 不适用：二进制逆向、系统提权、内网渗透
- 需要recon_agent提供Web服务信息作为输入

### exploit_agent（漏洞利用子智能体）
- 适用：漏洞验证与复现、Exploit开发、Payload生成、权限提升
- 不适用：初始侦察、代码审计
- 依赖上游智能体（web/code_audit/binary）提供漏洞信息

### code_audit_agent（代码审计子智能体）
- 适用：源代码安全审查、依赖漏洞检查、硬编码密钥发现、不安全配置检测
- 不适用：运行时渗透、端口扫描
- 可直接调度或由其他智能体触发

### binary_agent（二进制安全子智能体）
- 适用：逆向工程、缓冲区溢出、ROP链构造、Shellcode编写
- 不适用：Web安全、内网渗透
- 需要二进制文件作为输入

### internal_agent（内网渗透子智能体）
- 适用：横向移动、域攻击、凭据窃取、持久化、痕迹清理
- 不适用：外网侦察、Web扫描
- 依赖exploit_agent获得初始立足点

### report_agent（报告生成子智能体）
- 适用：汇总所有发现、生成结构化渗透测试报告
- 不适用：执行任何安全测试操作
- 应在所有安全测试完成后最后调度

### pentest_agent（通用渗透测试子智能体）
- 适用：跨领域渗透测试任务、未明确归类的安全需求、非标准安全测试
- 不适用：无明显限制（作为通用回退选项）
- 当任务无法明确归入其他专项智能体时使用

## 典型攻击链流水线
1. recon_agent（侦察）-> 2. web_agent/code_audit_agent/binary_agent（漏洞发现）-> 3. exploit_agent（利用）-> 4. internal_agent（内网渗透）-> 5. report_agent（报告）

## 调度原则
1. 任务明确对应某一子智能体 -> 直接调度该智能体
2. 任务模糊 -> 优先调度 recon_agent 做信息收集
3. 简单咨询/问答 -> 不调度，直接回复
4. 所有安全测试完成后 -> 调度 report_agent 生成报告
5. 前一步结果需要同类型深入 -> 可重复调度同一智能体
"""


# ==================== 上下文窗口管理 ====================

def trim_conversation_context(messages: list) -> list:
    """裁剪消息列表，保留 SystemMessage + 最近 15 条非系统消息"""
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]
    trimmed = system_msgs + non_system[-15:]
    return trimmed


# ==================== Analyzer 节点 ====================

def analyzer_node(state: AgentState):
    """
    意图分析节点 - 拆解用户任务并提取领域标签。
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent_analysis": "无用户输入", "task_plan": [], "task_context_tags": []}

    user_messages = [m for m in messages if isinstance(m, HumanMessage)]
    if not user_messages:
        return {}

    latest_user_msg = user_messages[-1]
    user_id = state.get("user_id")
    current_provider = state.get("current_provider", settings.DEFAULT_PROVIDER)
    current_model = state.get("current_model", settings.DEFAULT_MODEL)

    llm = get_llm(provider=current_provider, model=current_model)
    structured_llm = llm.with_structured_output(TaskBreakdown)

    system_prompt = SystemMessage(content="""你是一个安全任务分析器。分析用户输入，判断是否为需要拆解的复杂任务。

对于复杂任务（渗透测试、安全审计、漏洞挖掘等）：
- is_complex: true
- analysis: 深度理解用户意图
- steps: 拆解为3-7个具体步骤
- intent_tags: 提取领域标签（web/pwn/pentest/ctf/recon/exploit/binary/code_audit/internal/report 等），最多3个

对于简单任务（询问、闲聊、单一操作）：
- is_complex: false
- analysis: 简要说明用户需求
- steps: 空列表
- intent_tags: 空列表
""")

    try:
        breakdown: TaskBreakdown = structured_llm.invoke([system_prompt, latest_user_msg])
        print(f"\ud83d\udd0d [Analyzer] 任务分析: complex={breakdown.is_complex}, tags={breakdown.intent_tags}")

        # 更新用户画像标签
        if user_id and breakdown.intent_tags:
            auto_update_portrait_tags(user_id, breakdown.intent_tags)

        if breakdown.is_complex:
            return {
                "intent_analysis": breakdown.analysis,
                "task_plan": breakdown.steps,
                "task_context_tags": breakdown.intent_tags,
            }
        else:
            return {
                "intent_analysis": breakdown.analysis,
                "task_plan": [],
                "task_context_tags": [],
            }

    except Exception as e:
        print(f"\u26a0\ufe0f [Analyzer] 分析失败: {e}")
        return {
            "intent_analysis": "分析失败，交给 Manager 直接处理",
            "task_plan": [],
            "task_context_tags": [],
        }


# ==================== Manager 节点 ====================

def manager_node(state: AgentState):
    """
    Manager 决策节点 - 调度子智能体或直接回复用户。

    流程：
    1. 上下文分析（任务计划、上一步结果、用户画像）
    2. 消息裁剪（防上下文爆炸）
    3. LLM 结构化解码 -> DispatchDecision
    4. 按决策设置 subagent_dispatch
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    user_id = state.get("user_id")
    task_plan = state.get("task_plan", [])
    task_tags = state.get("task_context_tags", [])
    decision_history = state.get("decision_history", [])
    current_goal = state.get("current_goal", "")
    current_provider = state.get("current_provider", settings.DEFAULT_PROVIDER)
    current_model = state.get("current_model", settings.DEFAULT_MODEL)

    llm = get_llm(provider=current_provider, model=current_model)
    structured_llm = llm.with_structured_output(DispatchDecision)

    # ===== 上下文裁剪 =====
    trimmed_messages = trim_conversation_context(messages)
    if len(trimmed_messages) < len(messages):
        print(f"\ud83d\udce6 [Manager] 消息裁剪: {len(messages)} -> {len(trimmed_messages)}")

    # ===== 构建 System Prompt =====
    prompt_parts = [
        "你是一个网络安全专家调度智能体（Manager）。你的职责是分析当前对话状态，决定下一步行动。",
        "",
        "## 你可以做的两件事",
        "1. **调度子智能体**：将任务分派给 recon_agent / web_agent / exploit_agent / code_audit_agent / binary_agent / internal_agent / report_agent",
        "2. **直接回复用户**：如果任务已完成或只是咨询问题，直接回答",
        "",
        SUBAGENT_SELECTION_GUIDE,
    ]

    # 用户画像
    portrait = get_user_portrait_text(user_id)
    if portrait:
        prompt_parts.extend(["", "## 当前用户画像", portrait])

    # 任务计划
    if task_plan:
        plan_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(task_plan)])
        prompt_parts.extend(["", f"## 任务执行计划\n{plan_text}"])

    if current_goal:
        prompt_parts.extend(["", f"## 当前目标\n{current_goal}"])

    # 任务标签
    if task_tags:
        prompt_parts.extend(["", f"## 任务领域标签\n{', '.join(task_tags)}"])

    # 历史决策
    if decision_history:
        hist_lines = []
        for d in decision_history[-3:]:
            hist_lines.append(
                f"- 调度: {d.get('dispatch', 'N/A')} | "
                f"理由: {d.get('reasoning', '')[:60]}"
            )
        prompt_parts.extend(["", "## 最近调度记录", "\n".join(hist_lines)])

    # 子智能体经验
    experiences = get_dynamic_agent_experiences()
    if experiences and "还没有累积" not in experiences:
        prompt_parts.extend(["", f"## 子智能体历史经验\n{experiences}"])

    # 子智能体结果
    subagent_results = state.get("subagent_results", [])
    if subagent_results:
        result_lines = ["## 最近子智能体执行结果"]
        for r in subagent_results[-3:]:  # Last 3 results
            agent = r.get("agent_name", "unknown")
            status = r.get("status", "?")
            summary = r.get("summary", "")[:200]
            findings_count = len(r.get("findings", []))
            result_lines.append(f"- [{agent}] ({status}): {summary}")
            if findings_count:
                result_lines.append(f"  发现 {findings_count} 项")
            error = r.get("error")
            if error:
                result_lines.append(f"  错误: {error}")
        prompt_parts.extend(["", "\n".join(result_lines)])

        system_prompt = SystemMessage(content="\n".join(prompt_parts))

    # ===== LLM 调度决策 =====
    print(f"\ud83e\udde0 [Manager] 正在决策调度... ({current_provider}/{current_model})")

    try:
        decision: DispatchDecision = structured_llm.invoke([system_prompt] + trimmed_messages)
    except Exception as e:
        print(f"\u26a0\ufe0f [Manager] 结构化决策失败，降级为直接回复: {e}")
        response = llm.invoke([system_prompt] + trimmed_messages)
        return {
            "messages": [response],
            "subagent_dispatch": "",
        }

    # ===== 处理决策 =====
    print(f"\ud83d\udce3 [Manager] 决策: dispatch={decision.dispatch_target}, complete={decision.is_task_complete}")

    # 记录决策历史
    new_decision = {
        "dispatch": decision.dispatch_target or "direct_reply",
        "reasoning": decision.reasoning,
    }
    updated_history = (decision_history or []) + [new_decision]

    if decision.is_task_complete or decision.dispatch_target is None:
        # 任务完成 / 直接回复
        print("\u2705 [Manager] 任务完成或直接回复用户")
        final_prompt = SystemMessage(content=(
            "你是安全专家助手。根据以下决策分析，用自然友好的语言回复用户。\n"
            f"分析：{decision.situation_analysis}\n"
            "回复要简洁、专业、可操作。"
        ))
        response = llm.invoke([final_prompt] + trimmed_messages)
        return {
            "messages": [response],
            "subagent_dispatch": "",
            "decision_history": updated_history,
            "execution_phase": "complete",
        }
    else:
        # 调度子智能体
        print(f"\ud83d\ude80 [Manager] 调度 {decision.dispatch_target}，指令: {decision.task_instruction[:80]}...")
        dispatch_msg = AIMessage(content=(
            f"\ud83d\udd00 [调度决策] 分派给 {decision.dispatch_target}\n"
            f"推理：{decision.reasoning}\n"
            f"任务指令：{decision.task_instruction}"
        ))
        task_msg = HumanMessage(content=decision.task_instruction)

        return {
            "messages": [dispatch_msg, task_msg],
            "subagent_dispatch": decision.dispatch_target,
            "task_instruction": decision.task_instruction,
            "decision_history": updated_history,
            "execution_phase": "executing",
        }
