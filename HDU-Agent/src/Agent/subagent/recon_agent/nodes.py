# src/Agent/subagent/recon_agent/nodes.py
"""
Recon Agent node implementations.

Five nodes following the manager agent pattern:
  orchestrator -> worker <-> tools -> evaluator -> reporter

Each node is a factory function returning a callable for StateGraph.add_node().
"""
from typing import List, Callable, Dict, Any
from langchain_core.messages import (
    SystemMessage, AIMessage, HumanMessage, ToolMessage
)
from langchain_core.tools import BaseTool

from .state import ReconPlan, ReconFinding, ReconReport, StepEvaluation, ExecutionStep


# ==================== System Prompt ====================

RECON_AGENT_SYSTEM_PROMPT = """You are a Reconnaissance & Information Gathering Expert (Recon Agent).

## Your Mission
Execute comprehensive target reconnaissance covering the full recon chain:

1. **Passive Reconnaissance**: DNS enumeration, subdomain discovery, certificate transparency logs, WHOIS lookups, search engine dorking - all without directly touching the target.
2. **Active Scanning**: Port scanning, service detection, network mapping using controlled probes.
3. **Service Identification**: Banner grabbing, version detection, configuration fingerprinting for each discovered service.
4. **OS Fingerprinting**: Determine target operating system type and version via TTL analysis, TCP/IP stack fingerprinting, and service banners.
5. **Output Consolidation**: Generate a structured asset inventory with attack surface analysis.

## Output Standards
- **Asset Inventory**: IPs/domains, open ports, services with versions, OS type/version
- **Attack Surface Analysis**: Internet-facing services, potential vulnerability entry points, exposed admin interfaces
- **Next-Step Recommendations**: Which sub-agents to dispatch next (web_agent, exploit_agent, code_audit_agent, etc.)

## Rules
- Prefer non-intrusive techniques first; escalate to active scanning only when needed
- Respect rate limits; avoid aggressive scanning that could trigger IDS/IPS
- Output must be structured and machine-readable for downstream agents
- When uncertain, clearly state confidence level and recommend manual verification
"""

# ==================== Node: Orchestrator ====================

def make_orchestrator_node(agent_name: str, system_prompt: str) -> Callable:
    """Create the orchestrator node.

    Reads the task instruction from the latest HumanMessage and produces
    a structured ReconPlan using the LLM's structured output capability.
    """
    def orchestrator_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = state.get("messages", [])
        # Extract task instruction from the latest HumanMessage
        task_instruction = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                task_instruction = m.content
                break
        if not task_instruction:
            task_instruction = state.get("sa_task_instruction", "Execute reconnaissance on the specified target")

        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        plan_prompt = f"""You are the orchestrator for the {agent_name} security sub-agent.

## Agent Role
{system_prompt}

## Task Instruction
{task_instruction}

## Instructions
Break the reconnaissance task into 2-5 concrete execution steps.
Each step must have:
- phase: one of passive|active|service|fingerprint|report
- description: what to do
- tools_needed: expected tools
- expected_output: what should be produced

Generate the execution plan now."""

        structured_llm = llm.with_structured_output(ReconPlan)
        try:
            plan: ReconPlan = structured_llm.invoke([
                SystemMessage(content=plan_prompt),
                HumanMessage(content="Create the recon execution plan."),
            ])
        except Exception as e:
            print(f"[{agent_name}] Orchestrator structured output failed ({e}), using fallback plan")
            plan = ReconPlan(
                agent_name=agent_name,
                task_summary=task_instruction[:200],
                steps=[
                    ExecutionStep(step_number=1, phase="passive",
                                  description="Passive recon: DNS, WHOIS, certificate transparency",
                                  tools_needed=["dns_enum", "whois_lookup"],
                                  expected_output="Domain info, subdomains, WHOIS data"),
                    ExecutionStep(step_number=2, phase="active",
                                  description="Active port scanning on discovered targets",
                                  tools_needed=["port_scan"],
                                  expected_output="Open ports per host"),
                    ExecutionStep(step_number=3, phase="service",
                                  description="Service identification and banner grabbing",
                                  tools_needed=["service_detect", "banner_grab"],
                                  expected_output="Service names, versions, banners"),
                    ExecutionStep(step_number=4, phase="fingerprint",
                                  description="OS fingerprinting",
                                  tools_needed=["os_detect"],
                                  expected_output="OS type, version, confidence"),
                    ExecutionStep(step_number=5, phase="report",
                                  description="Consolidate findings into structured asset report",
                                  tools_needed=[],
                                  expected_output="Structured asset inventory with attack surface analysis"),
                ],
                success_criteria="All phases completed with structured asset inventory",
            )

        plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.dict()
        plan_msg_content = f"[{agent_name}] Recon Plan ({len(plan.steps)} steps):\n" + "\n".join(
            f"  Step {s.step_number} [{s.phase}]: {s.description}" for s in plan.steps
        )
        plan_msg = AIMessage(content=plan_msg_content)

        print(f"[{agent_name}] Orchestrator created plan with {len(plan.steps)} steps")

        return {
            "messages": [plan_msg],
            "sa_execution_plan": plan_dict,
            "sa_current_step": 0,
            "sa_phase": "executing",
            "sa_iteration_count": 0,
            "sa_max_iterations": state.get("sa_max_iterations", 8),
            "sa_agent_name": agent_name,
            "sa_findings": [],
            "sa_tool_history": [],
            "sa_last_error": "",
            "sa_retry_count": 0,
            "sa_max_retries": state.get("sa_max_retries", 2),
        }

    return orchestrator_node

# ==================== Node: Worker (ReAct Loop) ====================

def make_worker_node(agent_name: str, system_prompt: str, tools: List[BaseTool]) -> Callable:
    """Create the worker node for the ReAct loop.

    The worker:
    1. Reads the current step from the execution plan
    2. Uses LLM with tool binding to decide next action
    3. Returns tool_calls or final response
    """
    def worker_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = list(state.get("messages", []))
        plan = state.get("sa_execution_plan", {})
        current_step_idx = state.get("sa_current_step", 0)
        steps = plan.get("steps", []) if isinstance(plan, dict) else []

        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )
        llm_with_tools = llm.bind_tools(tools)

        # Build context for the current step
        current_step_info = ""
        if steps and current_step_idx < len(steps):
            step = steps[current_step_idx]
            current_step_info = (
                f"\n## Current Step ({current_step_idx + 1}/{len(steps)})\n"
                f"Phase: {step.get('phase', 'unknown')}\n"
                f"Goal: {step.get('description', 'Execute recon')}\n"
                f"Expected tools: {', '.join(step.get('tools_needed', []))}\n"
                f"Expected output: {step.get('expected_output', 'Recon results')}"
            )

        # Inject system prompt once
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            step_prompt = system_prompt + current_step_info
            messages = [SystemMessage(content=step_prompt)] + messages

        response = llm_with_tools.invoke(messages)

        iteration = state.get("sa_iteration_count", 0) + 1
        print(f"[{agent_name}] Worker iteration {iteration}, step {current_step_idx + 1}")

        return {
            "messages": [response],
            "sa_iteration_count": iteration,
        }

    return worker_node

# ==================== Node: Tools (Tool Execution) ====================

def make_tools_node(tools: List[BaseTool]) -> Callable:
    """Create the tools execution node with robust error handling.

    Executes tool calls from the most recent AIMessage and returns ToolMessages.
    """
    tools_by_name = {t.name: t for t in tools}

    def tools_node(state: dict) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        tool_messages = []
        tool_history = list(state.get("sa_tool_history", []) or [])

        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            tool = tools_by_name.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    result_str = str(result)
                except Exception as e:
                    result_str = f"Tool execution error: {str(e)}"
            else:
                result_str = f"Tool not found: {tool_name}"

            tool_messages.append(ToolMessage(
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            ))
            tool_history.append({
                "tool": tool_name,
                "args": tool_args,
                "result_preview": result_str[:500],
            })

        print(f"[{state.get('sa_agent_name', 'recon_agent')}] Tools executed: {[t.get('name', '?') for t in last_message.tool_calls]}")

        return {
            "messages": tool_messages,
            "sa_tool_history": tool_history,
        }

    return tools_node

# ==================== Node: Evaluator ====================

def make_evaluator_node(agent_name: str) -> Callable:
    """Create the evaluator node.

    After a worker step (no more tool_calls), evaluates the quality of results.
    Decides: retry current step, continue to next step, or abort and report.
    """
    def evaluator_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        messages = state.get("messages", [])
        plan = state.get("sa_execution_plan", {})
        current_step_idx = state.get("sa_current_step", 0)
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        retry_count = state.get("sa_retry_count", 0)
        max_retries = state.get("sa_max_retries", 2)
        iteration_count = state.get("sa_iteration_count", 0)
        max_iterations = state.get("sa_max_iterations", 8)
        existing_findings = state.get("sa_findings", []) or []

        agent_name_val = agent_name

        # Force completion conditions
        if iteration_count >= max_iterations:
            print(f"[{agent_name_val}] Max iterations ({max_iterations}) reached, forcing report")
            return {
                "sa_phase": "reporting",
                "sa_last_error": "Max iterations reached",
            }

        if not steps:
            print(f"[{agent_name_val}] No steps in plan, forcing report")
            return {"sa_phase": "reporting"}

        # Get current step info
        current_step = steps[current_step_idx] if current_step_idx < len(steps) else None
        step_description = current_step.get("description", "unknown") if current_step else "unknown"

        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        eval_prompt = f"""You are the evaluator for the {agent_name_val} recon sub-agent.

## Current Step ({current_step_idx + 1}/{len(steps)})
{step_description}

## Evaluation Criteria
1. Was meaningful recon data collected? (ports, services, banners, OS info)
2. Is the output quality sufficient for downstream agents?
3. Should this step be retried or can we move on?

## Instructions
Evaluate the latest execution results. Extract any new findings (assets, ports, services, OS info).
Decide whether to retry (up to {max_retries - retry_count} retries remaining),
continue to the next step, or abort entirely if results are unusable.

Generate the evaluation now."""

        structured_llm = llm.with_structured_output(StepEvaluation)
        try:
            eval_result: StepEvaluation = structured_llm.invoke([
                SystemMessage(content=eval_prompt),
                HumanMessage(content="Evaluate the latest recon step results."),
            ])
        except Exception as e:
            print(f"[{agent_name_val}] Evaluator structured output failed ({e}), auto-continue")
            return {
                "sa_current_step": current_step_idx + 1,
                "sa_phase": "reporting" if current_step_idx + 1 >= len(steps) else "executing",
                "sa_retry_count": 0,
            }

        # Merge extracted findings
        new_findings = eval_result.findings_extracted
        findings_dicts = []
        for f in existing_findings:
            if isinstance(f, dict):
                findings_dicts.append(f)
            elif hasattr(f, "model_dump"):
                findings_dicts.append(f.model_dump())
            elif hasattr(f, "dict"):
                findings_dicts.append(f.dict())
        for f in new_findings:
            if hasattr(f, "model_dump"):
                findings_dicts.append(f.model_dump())
            elif hasattr(f, "dict"):
                findings_dicts.append(f.dict())
            elif isinstance(f, dict):
                findings_dicts.append(f)

        print(f"[{agent_name_val}] Evaluator: completed={eval_result.step_completed}, "
              f"quality={eval_result.quality_score}/10, findings={len(findings_dicts)}")

        # Decision logic
        if eval_result.should_retry and retry_count < max_retries:
            print(f"[{agent_name_val}] Retrying step {current_step_idx + 1} (attempt {retry_count + 2})")
            return {
                "sa_retry_count": retry_count + 1,
                "sa_phase": "executing",
                "sa_findings": findings_dicts,
                "sa_last_error": eval_result.retry_reason,
            }
        elif not eval_result.should_continue:
            print(f"[{agent_name_val}] Aborting: {eval_result.abort_reason}")
            return {
                "sa_phase": "reporting",
                "sa_findings": findings_dicts,
                "sa_last_error": eval_result.abort_reason,
            }
        else:
            next_step = current_step_idx + 1
            if next_step >= len(steps):
                print(f"[{agent_name_val}] All {len(steps)} steps complete, moving to reporter")
                return {
                    "sa_current_step": next_step,
                    "sa_phase": "reporting",
                    "sa_findings": findings_dicts,
                    "sa_retry_count": 0,
                }
            else:
                print(f"[{agent_name_val}] Advancing to step {next_step + 1}/{len(steps)}")
                return {
                    "sa_current_step": next_step,
                    "sa_phase": "executing",
                    "sa_findings": findings_dicts,
                    "sa_retry_count": 0,
                }

    return evaluator_node

# ==================== Node: Reporter ====================

def make_reporter_node(agent_name: str) -> Callable:
    """Create the reporter node.

    Compiles all findings into a structured ReconReport and injects the result
    into the parent graph's `subagent_results` for the manager to consume.
    """
    def reporter_node(state: dict) -> dict:
        from src.core.llm_factory import get_llm

        plan = state.get("sa_execution_plan", {})
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        all_findings = state.get("sa_findings", []) or []
        current_step = state.get("sa_current_step", 0)
        last_error = state.get("sa_last_error", "")
        iteration_count = state.get("sa_iteration_count", 0)

        # Determine success status
        total_steps = len(steps)
        if current_step >= total_steps and not last_error:
            status = "success"
        elif all_findings:
            status = "partial"
        else:
            status = "failed"

        # Generate summary via LLM
        llm = get_llm(
            provider=state.get("current_provider"),
            model=state.get("current_model"),
        )

        # Build findings summary for the prompt
        findings_summary = ""
        for i, f in enumerate(all_findings[:20]):
            f_title = f.get("title", "?") if isinstance(f, dict) else "?"
            f_cat = f.get("category", "?") if isinstance(f, dict) else "?"
            f_host = f.get("host", "") if isinstance(f, dict) else ""
            f_port = f.get("port", "") if isinstance(f, dict) else ""
            loc = f"{f_host}:{f_port}" if f_port else f_host
            findings_summary += f"  {i+1}. [{f_cat}] {f_title} ({loc})\n"

        if not findings_summary:
            findings_summary = "  (No structured findings extracted)\n"

        summary_prompt = f"""You are the reporter for the {agent_name} recon sub-agent.

## Recon Status: {status}
Steps completed: {current_step}/{total_steps}

## Raw Findings:
{findings_summary}

## Instructions
Write a concise executive summary (3-5 sentences) of the reconnaissance results.
Then list 2-4 concrete next-step recommendations for downstream agents.
Focus on actionable intelligence: which targets/services warrant deeper investigation.

Respond with a plain text summary (no JSON needed)."""

        try:
            summary_response = llm.invoke([
                SystemMessage(content=summary_prompt),
                HumanMessage(content="Generate the recon summary and recommendations."),
            ])
            summary_text = summary_response.content
        except Exception as e:
            summary_text = f"Recon {status}: {current_step}/{total_steps} steps completed."
            print(f"[{agent_name}] Reporter LLM failed ({e}), using basic summary")

        # Build report
        report = ReconReport(
            agent_name=agent_name,
            status=status,
            summary=summary_text,
            findings=[],  # Pass raw dicts separately
            steps_executed=current_step,
            steps_total=total_steps,
            key_insights=[summary_text],
            next_recommendations=[
                "Dispatch web_agent for web vulnerability scanning on discovered HTTP services",
                "Dispatch exploit_agent if vulnerable services are identified",
                "Dispatch code_audit_agent for deeper analysis of exposed applications",
            ],
            errors_encountered=[last_error] if last_error else [],
        )

        # Build message for the parent graph
        findings_by_category = {}
        for f in all_findings:
            cat = f.get("category", "other") if isinstance(f, dict) else "other"
            findings_by_category.setdefault(cat, []).append(f)

        report_msg_parts = [
            f"[{agent_name}] Recon Complete ({status})",
            "",
            summary_text,
            "",
            f"Findings: {len(all_findings)} total",
        ]
        for cat, items in findings_by_category.items():
            report_msg_parts.append(f"  {cat}: {len(items)}")
        if last_error:
            report_msg_parts.append(f"\nError: {last_error}")

        report_msg = "\n".join(report_msg_parts)

        # Build SubAgentResult for parent graph consumption
        result_entry = {
            "agent_name": agent_name,
            "status": status,
            "summary": summary_text[:500],
            "findings": all_findings,
            "artifacts": [],
            "tokens_used": 0,
            "iterations": iteration_count,
            "error": last_error if status == "failed" else None,
        }

        existing_results = state.get("subagent_results") or []
        if isinstance(existing_results, list):
            updated_results = existing_results + [result_entry]
        else:
            updated_results = [result_entry]

        print(f"[{agent_name}] Reporter: status={status}, findings={len(all_findings)}")

        return {
            "messages": [AIMessage(content=report_msg)],
            "subagent_results": updated_results,
            "subagent_status": status,
            "sa_phase": "done",
            "execution_phase": "aggregating",
        }

    return reporter_node
