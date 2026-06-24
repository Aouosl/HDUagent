# src/Agent/manager/subagent_factory.py
"""
LangGraph sub-agent factory with multi-node architecture.

Each sub-agent is a compiled StateGraph with five nodes:
  orchestrator -> worker <-> tools
                    |
                    v
                evaluator -> reporter -> END

Key design principles:
- orchestrator: structured planning before execution
- worker: ReAct loop (LLM decision + tool calling)
- tools: tool execution with robust error handling
- evaluator: reflects on results, decides next step or abort
- reporter: compiles findings into structured SubAgentReport

Communication with parent manager:
- Shared `messages` list carries task instructions and final reports
- `subagent_results` dict holds the structured report for manager consumption
- `subagent_status` signals success/partial/failed to the manager
"""
from typing import List, Optional, Dict, Any, Callable, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import (
    SystemMessage, AIMessage, HumanMessage, ToolMessage
)
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from .subagent_models import (
    SubAgentPlan, SubAgentReport, Finding, StepEvaluation, ExecutionStep
)


# ==================== State ====================

# Keys that overlap with the parent AgentState must appear in both.
# Sub-agent-only keys use "sa_" prefix and are discarded when the
# subgraph returns control to the parent graph.

class SubAgentInternalState(BaseModel):
    """Typed state for the sub-agent internal graph (Pydantic for runtime use).

    LangGraph TypedDict approach is used at graph definition;
    this model helps us construct default values cleanly.
    """
    sa_task_instruction: str = ""
    sa_execution_plan: Optional[SubAgentPlan] = None
    sa_current_step: int = 0
    sa_findings: List[Finding] = []
    sa_tool_history: List[Dict[str, Any]] = []
    sa_iteration_count: int = 0
    sa_max_iterations: int = 5
    sa_agent_name: str = "unknown"
    sa_phase: str = "init"
    sa_last_error: str = ""
    sa_retry_count: int = 0
    sa_max_retries: int = 2


# ==================== Node Implementations ====================

def make_orchestrator_node(
    agent_name: str,
    system_prompt: str,
) -> Callable:
    """Create the orchestrator node that produces a structured execution plan.

    The orchestrator reads the task instruction from the latest HumanMessage
    and produces a SubAgentPlan using the LLM's structured output.
    """
    def orchestrator_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = state.get("messages", [])
        task_instruction = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                task_instruction = m.content
                break

        if not task_instruction:
            task_instruction = state.get("sa_task_instruction", "Execute assigned security task")

        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        plan_prompt = f"""You are the orchestrator for the {agent_name} security sub-agent.

Your task is to create a concrete, structured execution plan.

## Agent Role
{system_prompt}

## Task Instruction
{task_instruction}

## Instructions
Break the task into 2-5 concrete execution steps. Each step must have:
- A clear description of what to do
- Expected tools (if any)
- Expected output

Generate the plan now."""
        
        structured_llm = llm.with_structured_output(SubAgentPlan)
        try:
            plan: SubAgentPlan = structured_llm.invoke([
                SystemMessage(content=plan_prompt),
                HumanMessage(content="Create the execution plan for this task."),
            ])
        except Exception:
            # Fallback: simple single-step plan
            plan = SubAgentPlan(
                agent_name=agent_name,
                task_summary=task_instruction[:200],
                steps=[ExecutionStep(
                    step_number=1,
                    phase="execute",
                    description=task_instruction,
                    expected_output="Task results",
                )],
                success_criteria="Task instruction completed",
            )

        plan_msg = AIMessage(content=f"[{agent_name}] Execution Plan ({len(plan.steps)} steps):\n" + "\n".join(
            f"  Step {s.step_number} [{s.phase}]: {s.description}" for s in plan.steps
        ))
        
        print(f"[{agent_name}] Orchestrator created plan with {len(plan.steps)} steps")

        return {
            "messages": [plan_msg],
            "sa_execution_plan": plan.model_dump() if hasattr(plan, 'model_dump') else plan.dict(),
            "sa_current_step": 0,
            "sa_total_steps": len(plan.steps),
            "sa_iteration_count": 0,
            "sa_findings": [],
            "sa_tool_history": [],
            "sa_phase": "executing",
            "sa_agent_name": agent_name,
            "sa_retry_count": 0,
            "execution_phase": "executing",
        }

    return orchestrator_node


def make_worker_node(
    agent_name: str,
    system_prompt: str,
    tools: List[BaseTool],
) -> Callable:
    """Create the worker (ReAct) node that makes LLM decisions and calls tools.

    The worker receives the current plan step and decides what tool to call.
    """
    def worker_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = list(state.get("messages", []))
        plan_dict = state.get("sa_execution_plan", {})
        current_step = state.get("sa_current_step", 0)
        findings = state.get("sa_findings", [])
        iteration = state.get("sa_iteration_count", 0) + 1
        max_iter = state.get("sa_max_iterations", 5)

        # Enforce max iterations
        if iteration > max_iter:
            print(f"[{agent_name}] Max iterations ({max_iter}) reached, forcing completion")
            return {
                "sa_iteration_count": iteration,
                "sa_phase": "evaluating",
            }

        # Build step context
        steps = plan_dict.get("steps", [])
        current_step_desc = ""
        if steps and current_step < len(steps):
            s = steps[current_step]
            current_step_desc = f"Step {s.get('step_number', current_step+1)} [{s.get('phase', 'execute')}]: {s.get('description', '')}"
            if s.get("expected_output"):
                current_step_desc += f"\nExpected output: {s.get('expected_output')}"

        # Build findings context
        findings_context = ""
        if findings:
            findings_lines = [f"- [{f['severity']}] {f['title']}" for f in findings[-5:]]
            findings_context = "Findings so far:\n" + "\n".join(findings_lines)

        # Inject system prompt only on first call
        if not any(isinstance(m, SystemMessage) for m in messages):
            step_instruction = f"""You are the {agent_name} security sub-agent.

## Your Role
{system_prompt}

## Current Task
{current_step_desc}

Use the available tools to accomplish this step. Output your findings clearly.
When the current step is complete, respond with a summary and do NOT call more tools."""
            messages = [SystemMessage(content=step_instruction)] + messages

            if findings_context:
                messages.insert(1, SystemMessage(content=findings_context))

        # If we are resuming after evaluator feedback, add context
        last_error = state.get("sa_last_error", "")
        if last_error:
            messages.append(HumanMessage(content=f"Previous attempt had issues: {last_error}\nPlease adjust your approach and try again."))

        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )
        llm_with_tools = llm.bind_tools(tools)

        response = llm_with_tools.invoke(messages)
        print(f"[{agent_name}] Worker iteration {iteration}: tool_calls={bool(response.tool_calls)}")

        return {
            "messages": [response],
            "sa_iteration_count": iteration,
            "sa_phase": "executing",
            "sa_last_error": "",  # Clear on new attempt
        }

    return worker_node


def make_tools_node(tools: List[BaseTool]) -> Callable:
    """Create the tool execution node using LangGraph's prebuilt ToolNode."""
    tools_by_name = {t.name: t for t in tools}
    tool_node = ToolNode(tools)

    # Wrap to add tool history tracking
    def wrapped_tool_node(state: dict) -> dict:
        result = tool_node(state)
        
        # Track tool history
        tool_history = list(state.get("sa_tool_history", []))
        tool_msgs = result.get("messages", [])
        for msg in tool_msgs:
            if isinstance(msg, ToolMessage):
                tool_history.append({
                    "tool": msg.name,
                    "status": "success" if "error" not in str(msg.content).lower() else "error",
                    "content_preview": str(msg.content)[:200],
                })
        
        result["sa_tool_history"] = tool_history
        return result

    return wrapped_tool_node


def make_evaluator_node(agent_name: str) -> Callable:
    """Create the evaluator node that reflects on worker output and decides next action.

    Evaluator decision outcomes:
    - "retry": Retry the current step (e.g., tool failed, unclear output)
    - "continue": Move to the next plan step
    - "done": All steps complete, proceed to reporter
    - "abort": Critical failure, go to reporter with partial results
    """
    def evaluator_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = state.get("messages", [])
        plan_dict = state.get("sa_execution_plan", {})
        current_step = state.get("sa_current_step", 0)
        total_steps = state.get("sa_total_steps", 1)
        retry_count = state.get("sa_retry_count", 0)
        max_retries = state.get("sa_max_retries", 2)
        iteration = state.get("sa_iteration_count", 0)
        max_iter = state.get("sa_max_iterations", 5)

        # Get the last few messages for evaluation
        recent_msgs = messages[-6:]  # Last 3 exchanges

        # Check for max iteration early exit
        if iteration >= max_iter:
            print(f"[{agent_name}] Evaluator: max iteration reached")
            return {
                "sa_phase": "reporting",
                "sa_current_step": current_step + 1,  # Mark as done to trigger reporter
            }

        # Get the last AIMessage (worker output)
        last_ai = None
        for m in reversed(messages):
            if isinstance(m, AIMessage) and not m.tool_calls:
                last_ai = m
                break

        if last_ai is None:
            # Worker hasn't produced a non-tool-call response yet
            # Check if we should continue or something is wrong
            if retry_count < max_retries:
                print(f"[{agent_name}] Evaluator: no final output yet, retrying")
                return {
                    "sa_retry_count": retry_count + 1,
                    "sa_last_error": "No final response produced",
                    "sa_phase": "executing",
                }
            else:
                print(f"[{agent_name}] Evaluator: max retries for current step")
                return {
                    "sa_phase": "reporting",
                    "sa_current_step": current_step + 1,
                }

        # Use LLM to evaluate the step output
        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        step_desc = ""
        steps = plan_dict.get("steps", [])
        if steps and current_step < len(steps):
            s = steps[current_step]
            step_desc = f"Step {s.get('step_number', current_step+1)}: {s.get('description', '')}"

        eval_prompt = f"""You are the evaluator for the {agent_name} sub-agent.
Evaluate whether the current step was completed successfully.

## Current Step
Step {current_step+1}/{total_steps}: {step_desc}

## Worker Output
{last_ai.content[:1000]}

## Decision Rules
- If the step achieved its goal: should_continue=true, step_completed=true
- If the step failed but retry might help (different approach): should_retry=true
- If the step failed and retry won't help: should_continue=true, step_completed=false
- If this is a critical failure making further work impossible: should_continue=false
- If all steps are done (current_step >= total_steps-1): should_continue=true, step_completed=true

Make your evaluation."""

        structured_llm = llm.with_structured_output(StepEvaluation)
        try:
            evaluation: StepEvaluation = structured_llm.invoke([
                SystemMessage(content=eval_prompt),
                HumanMessage(content="Evaluate the step execution."),
            ])
        except Exception as e:
            print(f"[{agent_name}] Evaluator structured output failed: {e}")
            # Default: move forward
            evaluation = StepEvaluation(
                step_completed=True,
                quality_score=5,
                should_retry=False,
                should_continue=True,
            )

        # Accumulate findings
        existing_findings = list(state.get("sa_findings", []))
        new_findings = []
        if evaluation.findings_extracted:
            for f in evaluation.findings_extracted:
                new_findings.append(f.model_dump() if hasattr(f, 'model_dump') else f.dict())
        all_findings = existing_findings + new_findings

        # Decision logic
        next_step = current_step
        next_phase = "executing"
        eval_msg_parts = [f"[{agent_name}] Step {current_step+1}/{total_steps} evaluation:"]

        if evaluation.should_retry and retry_count < max_retries:
            next_phase = "executing"
            eval_msg_parts.append(f"- Will retry: {evaluation.retry_reason}")
            result_update = {
                "sa_retry_count": retry_count + 1,
                "sa_last_error": evaluation.retry_reason,
                "sa_phase": next_phase,
            }
        elif evaluation.should_continue:
            next_step = current_step + 1
            eval_msg_parts.append(f"- {'Completed' if evaluation.step_completed else 'Moving on'} (quality: {evaluation.quality_score}/10)")
            if next_step >= total_steps:
                next_phase = "reporting"
                eval_msg_parts.append("- All steps done, proceeding to report")
            else:
                next_phase = "executing"
                if evaluation.next_step_adjustment:
                    eval_msg_parts.append(f"- Next step adjustment: {evaluation.next_step_adjustment}")
            result_update = {
                "sa_current_step": next_step,
                "sa_retry_count": 0,
                "sa_last_error": "",
                "sa_phase": next_phase,
            }
        else:
            # Abort
            next_phase = "reporting"
            eval_msg_parts.append(f"- Aborting: {evaluation.abort_reason}")
            result_update = {
                "sa_current_step": total_steps,  # Force reporting
                "sa_phase": "reporting",
                "sa_last_error": evaluation.abort_reason,
            }

        result_update["messages"] = [AIMessage(content="\n".join(eval_msg_parts))]
        result_update["sa_findings"] = all_findings
        if evaluation.issues:
            result_update["sa_last_error"] = "; ".join(evaluation.issues)

        print(f"[{agent_name}] Evaluator: phase={next_phase}, step={next_step}/{total_steps}")
        return result_update

    return evaluator_node


def make_reporter_node(agent_name: str) -> Callable:
    """Create the reporter node that compiles final structured output into messages.

    The reporter:
    1. Compiles all findings into a SubAgentReport
    2. Writes the report to subagent_results for manager consumption
    3. Appends a concise summary to messages for human readability
    """
    def reporter_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        all_findings = state.get("sa_findings", [])
        messages = state.get("messages", [])
        plan_dict = state.get("sa_execution_plan", {})
        current_step = state.get("sa_current_step", 0)
        total_steps = state.get("sa_total_steps", 0)
        last_error = state.get("sa_last_error", "")
        tool_history = state.get("sa_tool_history", [])

        # Determine status
        if current_step >= total_steps and not last_error:
            status = "success"
        elif current_step > 0:
            status = "partial"
        else:
            status = "failed"

        # Extract task instruction
        task_instruction = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                task_instruction = m.content
                break

        # Use LLM to generate a concise summary
        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        findings_text = ""
        if all_findings:
            findings_text = "\n".join(
                f"- [{f.get('severity', 'Info')}] {f.get('title', 'Unknown')}: {f.get('description', '')[:120]}"
                for f in all_findings
            )

        summary_prompt = f"""You are the reporter for the {agent_name} sub-agent.
Generate a concise (3-5 sentence) executive summary of what was accomplished.

Task: {task_instruction[:300]}
Status: {status}
Steps completed: {current_step}/{total_steps}
Findings: {len(all_findings)} items
Errors: {last_error if last_error else 'None'}

Findings detail:
{findings_text[:500] if findings_text else 'No findings recorded'}

Write the summary now."""

        try:
            response = llm.invoke([SystemMessage(content=summary_prompt)])
            summary = response.content
        except Exception as e:
            summary = f"{agent_name} completed execution. Status: {status}. {current_step}/{total_steps} steps done. {len(all_findings)} findings."

        # Build structured report for manager
        findings_objects = []
        for f in all_findings:
            try:
                findings_objects.append(Finding(**f))
            except Exception:
                pass

        report = SubAgentReport(
            agent_name=agent_name,
            status=status,
            summary=summary,
            findings=findings_objects,
            steps_executed=current_step,
            steps_total=total_steps,
            errors_encountered=[last_error] if last_error else [],
        )

        # Compile message for the messages channel
        report_msg = f"[{agent_name}] Task Complete ({status})\n\n{summary}\n"
        if all_findings:
            report_msg += f"\nFindings ({len(all_findings)}):\n" + "\n".join(
                f"- [{f.get('severity','?')}] {f.get('title','?')}" for f in all_findings[:10]
            )
            if len(all_findings) > 10:
                report_msg += f"\n...and {len(all_findings)-10} more"

        print(f"[{agent_name}] Reporter: status={status}, findings={len(all_findings)}")

        # Build SubAgentResult-compatible dict
        report_dict = report.model_dump() if hasattr(report, 'model_dump') else report.dict()
        result_entry = {
            "agent_name": agent_name,
            "status": status,
            "summary": summary,
            "findings": [f for f in all_findings],
            "artifacts": [],
            "tokens_used": 0,
            "iterations": state.get("sa_iteration_count", 0),
            "error": last_error if status == "failed" else None,
        }
        
        existing_results = state.get("subagent_results") or []
        if isinstance(existing_results, list):
            updated_results = existing_results + [result_entry]
        else:
            updated_results = [result_entry]

        return {
            "messages": [AIMessage(content=report_msg)],
            "subagent_results": updated_results,
            "subagent_status": status,
            "sa_phase": "done",
            "execution_phase": "aggregating",
        }

    return reporter_node


# ==================== Graph Assembly ====================

def create_domain_subgraph(
    agent_name: str,
    system_prompt: str,
    tools: Optional[List[BaseTool]] = None,
    max_iterations: int = 5,
    max_retries: int = 2,
) -> StateGraph:
    """Create a domain-specific LangGraph sub-agent with multi-node architecture.

    Internal graph structure:
    
    orchestrator --> worker <---> tools
                       |
                       v (no tool_calls)
                   evaluator
                    /  |  \
              retry   continue   done/abort
                |       |           |
                v       v           v
              worker  worker     reporter --> END

    Args:
        agent_name: Sub-agent identifier for logging and routing
        system_prompt: Domain-specific system prompt
        tools: Tools available to this sub-agent (None = all common tools)
        max_iterations: Maximum ReAct loop iterations before forced completion
        max_retries: Maximum retries per step before moving on

    Returns:
        Compiled StateGraph subgraph ready to be added as a node in the parent graph
    """
    from src.tools.registery import get_all_tools
    tools = tools or get_all_tools()

    # Create node functions
    orchestrator_fn = make_orchestrator_node(agent_name, system_prompt)
    worker_fn = make_worker_node(agent_name, system_prompt, tools)
    tools_fn = make_tools_node(tools)
    evaluator_fn = make_evaluator_node(agent_name)
    reporter_fn = make_reporter_node(agent_name)

    # Build the graph
    workflow = StateGraph(dict)

    workflow.add_node("orchestrator", orchestrator_fn)
    workflow.add_node("worker", worker_fn)
    workflow.add_node("tools", tools_fn)
    workflow.add_node("evaluator", evaluator_fn)
    workflow.add_node("reporter", reporter_fn)

    workflow.set_entry_point("orchestrator")
    workflow.add_edge("orchestrator", "worker")

    # Routing from worker: has tool_calls -> tools, else -> evaluator
    def route_after_worker(state: dict) -> Literal["tools", "evaluator"]:
        messages = state.get("messages", [])
        if not messages:
            return "evaluator"
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
            return "tools"
        return "evaluator"

    workflow.add_conditional_edges("worker", route_after_worker, {
        "tools": "tools",
        "evaluator": "evaluator",
    })
    workflow.add_edge("tools", "worker")

    # Routing from evaluator: retry/continue -> worker, done/abort -> reporter
    def route_after_evaluator(state: dict) -> Literal["worker", "reporter"]:
        phase = state.get("sa_phase", "executing")
        if phase == "reporting":
            return "reporter"
        return "worker"

    workflow.add_conditional_edges("evaluator", route_after_evaluator, {
        "worker": "worker",
        "reporter": "reporter",
    })
    workflow.add_edge("reporter", END)

    compiled = workflow.compile()
    compiled.name = agent_name
    return compiled
