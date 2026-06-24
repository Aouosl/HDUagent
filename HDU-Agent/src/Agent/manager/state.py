# src/Agent/manager/state.py
"""
HDU-Agent 增强状态定义

支持：
- 多子智能体并行调度（fan-out / fan-in）
- 每个子智能体的结构化输出
- 子智能体内部规划-执行-反思-总结循环
- 执行历史追踪
"""
from typing import Annotated, TypedDict, Optional, List, Any, Dict
from langgraph.graph.message import add_messages


# ==================== 子智能体执行记录 ====================

class SubAgentResult(TypedDict, total=False):
    """单个子智能体执行完成后的结构化结果"""
    agent_name: str                          # 子智能体名称
    status: str                              # "success" / "failure" / "partial"
    summary: str                             # 人类可读的执行摘要
    findings: Optional[List[Dict[str, Any]]] # 结构化发现列表
    artifacts: Optional[List[str]]           # 产出物（如报告路径、截图路径）
    tokens_used: int                         # Token 消耗
    iterations: int                          # ReAct 迭代次数
    error: Optional[str]                     # 失败原因


# ==================== 主图 AgentState ====================

class AgentState(TypedDict):
    """LangGraph 主图共享状态"""
    # ---- 消息流 ----
    messages: Annotated[list, add_messages]

    # ---- 用户/会话上下文 ----
    user_api_keys: dict
    user_id: Optional[int]
    current_provider: Optional[str]
    current_model: Optional[str]

    # ---- Analyzer 输出 ----
    intent_analysis: Optional[str]           # 意图深度分析
    task_plan: Optional[List[str]]           # 分解后的执行步骤
    task_context_tags: Optional[List[str]]   # 任务领域标签
    task_complexity: Optional[str]           # "simple" / "medium" / "complex"

    # ---- Manager 决策 ----
    current_goal: Optional[str]              # 当前子目标描述
    decision_history: Optional[List[Dict[str, Any]]]  # 调度决策历史
    subagent_dispatch: Optional[str]         # 单次调度目标（DEPRECATED: 改为 parallel_dispatches）
    task_instruction: Optional[str]          # 给子智能体的任务指令

    # ---- 并行调度（新） ----
    # 当 Manager 决定并行调用多个子智能体时，填入此列表
    # 每个元素：{"agent": "recon_agent", "instruction": "扫描 target"}
    parallel_dispatches: Optional[List[Dict[str, str]]]

    # ---- 子智能体结果聚合 ----
    subagent_results: Optional[List[SubAgentResult]]  # 已完成子智能体的结果

    # ---- 重试控制 ----
    last_tool_status: Optional[str]
    last_tool_name: Optional[str]
    last_tool_args: Optional[Dict[str, Any]]
    retry_count: int
    max_retries: int

    # ---- 执行阶段标记 ----
    # 用于控制 Manager->子智能体->Manager 循环的阶段
    execution_phase: Optional[str]           # "analyzing" / "dispatching" / "executing" / "aggregating" / "complete"


# ==================== 子智能体内部状态 ====================

class SubAgentInternalState(TypedDict):
    """子智能体内部增强状态（plan → act ⇄ tools → reflect → summarize）"""
    messages: Annotated[list, add_messages]  # 与父图共享的消息流

    # ---- 规划阶段 ----
    plan: Optional[List[str]]                # 分解的子步骤
    current_step_index: int                  # 当前执行到第几步

    # ---- 执行追踪 ----
    tool_call_count: int                     # 工具调用总次数
    max_iterations: int                      # 最大迭代次数
    step_results: Optional[List[Dict[str, Any]]]  # 每步执行结果

    # ---- 反思阶段 ----
    reflection_notes: Optional[str]          # 自我反思笔记
    needs_retry: bool                        # 是否需要重试当前步骤
    retry_reason: Optional[str]              # 重试原因

    # ---- 总结阶段 ----
    final_summary: Optional[str]             # 最终总结
    structured_output: Optional[Dict[str, Any]]  # 结构化输出（schema由各子智能体定义）

    # ---- 控制流 ----
    agent_name: str                          # 子智能体名称（用于日志）
    system_prompt: str                       # 领域 system prompt
