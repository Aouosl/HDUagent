from __future__ import annotations

import asyncio
import json
import os
import re
import time
import requests  # 新增的依赖，用于发送 OpenAI 协议请求
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.task_memory import TaskMemory
from agent.playbook_router import PlaybookRouter


def build_advisor_prompt(task: str, summary: str, failures_text: str,
                          successful_outputs: str = "") -> str:
    return f"""You are a senior CTF/security advisor providing strategic guidance to an attacker agent.

## Your Mindset
You are a second pair of eyes — not a critic, not a cheerleader. Your value is seeing what the attacker can't: blind spots, false assumptions, and unexplored angles. But you MUST first understand what they've actually done.

### Rule 1: Read Before You Judge
Before giving ANY advice, you must:
1. Identify what the attacker HAS successfully done (tools that returned data)
2. Identify what concrete data they already possess
3. Only THEN identify what's missing or wrong
If the attacker has already found a file, read its contents, and extracted data from it — DO NOT tell them they haven't found the file. This sounds obvious but is your #1 failure mode.

### Rule 2: Trust Facts, Question Interpretations
- Tool outputs (server responses, command results, file listings) are ground truth
- The attacker's CONCLUSIONS about those outputs may be wrong
- "The command returned empty" is a fact — whether that means "wrong filter" or
   "no such traffic exists" is an interpretation you should help evaluate

### Rule 3: Don't Relitigate Success
If a technique produced meaningful results, build on it — don't suggest abandoning it just to sound contrarian. If the attacker already has the filename and is successfully running tshark against it, do NOT say "you need to find the filename first."

### Rule 4: Diagnose Direction vs Execution
Before advising, explicitly state which case you're seeing:
- **Wrong direction**: The attacker is looking in the wrong place entirely
- **Right direction, wrong execution**: The approach is sound but the implementation has bugs
- **Right direction, needs to stop**: The attacker has enough data but isn't synthesizing it
- **Right direction, incomplete**: More specific analysis is needed in a particular area

## Context
**Challenge objective:** {task[:500]}

**What the attacker has successfully obtained (GROUND TRUTH — do not contradict):**
{successful_outputs or "No successful outputs recorded yet."}

**Attacker's current understanding:**
{summary}

**Recent failed/empty attempts:**
{failures_text}

## Your Response
1. **Status assessment** — Which of the four cases above applies? State it explicitly.
2. **What they already have** — Briefly acknowledge concrete data the attacker has collected. Do NOT skip this step.
3. **What's actually missing** — Be specific. Name the gap between current data and the goal.
4. **Recommended next move** — ONE concrete, actionable step. Not a menu — a single best bet.

If the attacker appears to have enough data to write their conclusion, say so directly:
"You have sufficient data. Stop analyzing and write your report/conclusion now."

Be direct. ≤ 200 words. No code blocks unless illustrating a specific command. Strategy only."""


WEB_SYSTEM_PROMPT = """
You are a senior cybersecurity researcher performing authorized analysis in a local lab environment.

## Identity
You think like a real practitioner: methodical, adaptive, and outcome-oriented.
You don't spray commands hoping something sticks — you form hypotheses, test them,
and interpret results (including negative results) as data points toward your conclusion.

## Principles
- **Depth over breadth.** Understand what you're looking at before acting.
  Read tool outputs carefully. A command returning empty is not a failure —
  it's information (e.g., "no HTTP traffic exists in this capture").
- **Iterate with intent.** Each step should be informed by the last.
  If something returns empty or fails, diagnose WHY before trying again.
  Never repeat the exact same command expecting different results.
- **Negative results are results.** "No HTTP requests found" means the traffic
  is not HTTP-based — that's a finding, not a reason to retry the same filter.
  Incorporate it into your analysis and move on.
- **Precision tooling.** For binary formats (pcap, ELF, etc.), always use
  structured parsers (tshark, binwalk, readelf). Never dump raw bytes.
  When output is large, redirect to file and extract what matters.
- **Think in layers.** Network stack, application protocol, payload content —
  reason about which layer holds the answer and operate there.

## Knowing When to Stop
You MUST track what you've already learned. Before running any new command, ask yourself:
1. What do I already know from previous outputs?
2. What specific question would this new command answer?
3. Have I already asked this question (or an equivalent one)?

When you have enough data to form a professional conclusion — even if that conclusion
is "the traffic appears benign" or "analysis is limited by encrypted payloads" —
STOP ANALYZING AND WRITE YOUR CONCLUSION.

Signs you have enough data:
- You've characterized the protocol distribution
- You've identified the top talkers and conversation patterns
- You've checked for common attack indicators (port scans, sensitive ports, unusual patterns)
- You've attempted application-layer inspection and determined what's available
- Running more commands would only confirm what you already know

## Environment
You are running inside a Docker container (Kali Linux based). All targets are in-scope.
All target files are in /workspace/. Use the `shell` tool to execute any Linux command directly.
Available tools: tshark, nmap, tcpdump, sqlmap, gobuster, binwalk, john, python3, curl, netcat, etc.
File paths are always under /workspace/. Do not use Windows paths or WSL commands.

You have access to:
- `shell` — execute any Linux command directly in the container
- `python_sandbox` — for scripting and data processing
- `write_file` — for outputting reports and conclusions

## Output Protocol
When your task is Cybersecurity Analysis:
- Write a professional conclusion in Chinese (unless specified otherwise)
- Include: traffic overview, identified threats/anomalies, risk assessment, recommendations
- Save the report to the workspace directory
- Findings based on negative results (e.g., "no application-layer payloads detected")
  are equally valid and should be reported as such

When your task is CTF Flag Hunting:
- Follow the flag submission protocol
- Be creative with attack vectors; don't fixate on one approach

## Tool Usage Rule
You MUST call exactly ONE tool per response. Never call multiple tools in parallel.
After each tool result, decide your next single action.
Think step by step — one tool call at a time.
""".strip()

CONTEXT_WINDOW_MAX_MESSAGES = 30
ADVISOR_INTERVAL = 15
FORCE_CONCLUSION_ROUND = 60
SUCCESSFUL_FINDINGS_THRESHOLD = 10


class WebCTFAgent:
    def __init__(
            self,
            client,
            tools,
            runs_dir: str = "./runs",
            max_rounds: int = 40,
            memory: Optional[TaskMemory] = None,
            mcp_configs: Optional[List[StdioServerParameters]] = None,
            playbooks_dir: str = "./playbooks",
    ) -> None:
        self.client = client
        self.tools = tools
        self.runs_dir = runs_dir
        self.max_rounds = max_rounds
        self.memory = memory
        self.mcp_configs = mcp_configs or []
        self._advisor_called_count = 0
        self.successful_findings: List[Dict[str, Any]] = []
        self.playbook_router = PlaybookRouter(playbooks_dir)
        os.makedirs(self.runs_dir, exist_ok=True)

    # ==========================
    # [新增] 协议自适应翻译层
    # ==========================
    async def _create_message_adaptive(self, messages, tools, max_tokens, effort="high"):
        """智能路由：根据模型名称决定走 Claude 原生协议还是 OpenAI 兼容协议"""
        model = self.client.model.lower()
        if "claude" not in model:
            # DeepSeek, Qwen, GPT 等模型，走本地翻译为 OpenAI 协议
            return await asyncio.to_thread(self._call_openai_protocol, messages, tools, max_tokens)
        else:
            # Claude 模型，保持使用原生 Anthropic 协议
            return await asyncio.to_thread(
                self.client.create_message,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                effort=effort,
                stream=False
            )

    def _call_openai_protocol(self, windowed_messages, tools_def, max_tokens):
        """将 Claude 的历史记录和工具格式翻译为标准的 OpenAI /chat/completions 格式"""
        openai_msgs = []
        for m in windowed_messages:
            role = m["role"]
            content = m["content"]
            if role == "user":
                if isinstance(content, str):
                    openai_msgs.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    text_parts = []
                    for b in content:
                        if b.get("type") == "text":
                            text_parts.append(b["text"])
                        elif b.get("type") == "tool_result":
                            # 提取工具执行结果并转换为 OpenAI 的 tool role
                            openai_msgs.append({
                                "role": "tool",
                                "tool_call_id": b["tool_use_id"],
                                "content": str(b.get("content", ""))
                            })
                    if text_parts:
                        openai_msgs.append({"role": "user", "content": "\n".join(text_parts)})
            elif role == "assistant":
                if isinstance(content, str):
                    openai_msgs.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    text_parts = []
                    tool_calls = []
                    for b in content:
                        if b.get("type") == "text":
                            text_parts.append(b["text"])
                        elif b.get("type") == "tool_use":
                            tool_calls.append({
                                "id": b["id"],
                                "type": "function",
                                "function": {
                                    "name": b["name"],
                                    "arguments": json.dumps(b["input"])
                                }
                            })
                    msg = {"role": "assistant"}
                    if text_parts:
                        msg["content"] = "\n".join(text_parts)
                    if tool_calls:
                        msg["tool_calls"] = tool_calls
                    openai_msgs.append(msg)

        # 工具参数格式转换
        openai_tools = None
        if tools_def:
            openai_tools = []
            for t in tools_def:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("input_schema", {})
                    }
                })

        payload = {
            "model": self.client.model,
            "messages": openai_msgs,
            "max_tokens": max_tokens
        }
        if openai_tools:
            payload["tools"] = openai_tools

        # 从现有的 Claude 客户端中提取 API Key
        api_key = self.client.headers.get("Authorization", "").replace("Bearer ", "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # 强制将终点修正为 OpenAI 标准路由
        base_url = self.client.base_url.rstrip("/")
        endpoint = f"{base_url}/v1/chat/completions"
        timeout = getattr(self.client, "timeout_sec", 90)

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from OpenAI API: {resp.text}")
        
        data = resp.json()
        message = data["choices"][0]["message"]
        
        # 将大模型返回的 OpenAI 格式翻译回 Agent 内部使用的 Claude 格式
        anthropic_content = []
        if message.get("content"):
            anthropic_content.append({"type": "text", "text": message["content"]})

        for tc in message.get("tool_calls", []):
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}
            anthropic_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["function"]["name"],
                "input": args
            })

        return {
            "stop_reason": data["choices"][0].get("finish_reason"),
            "content": anthropic_content
        }
    # ==========================

    def _new_run_log(self) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(self.runs_dir, f"run-{ts}.jsonl")
        return path

    def _log_jsonl(self, path: str, obj: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    @staticmethod
    def _apply_sliding_window(
        messages: List[Dict[str, Any]],
        max_messages: int = CONTEXT_WINDOW_MAX_MESSAGES,
    ) -> List[Dict[str, Any]]:
        if len(messages) <= max_messages:
            return messages
        first_msg = messages[0]
        recent = messages[-(max_messages - 1):]
        if recent and recent[0]["role"] == "assistant":
            recent = recent[1:]
        return [first_msg] + recent

    def _inject_memory_update(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.memory:
            return messages
        summary = self.memory.get_working_memory_summary()
        memory_block = f"\n\n[System Update: Current Memory]\n{summary}"
        if not messages:
            return messages
        msgs = list(messages)
        last = msgs[-1]
        if last["role"] == "user":
            if isinstance(last["content"], str):
                msgs[-1] = {**last, "content": last["content"] + memory_block}
            elif isinstance(last["content"], list):
                msgs[-1] = {
                    **last,
                    "content": last["content"] + [{"type": "text", "text": memory_block}]
                }
        return msgs

    @staticmethod
    def _enforce_single_tool_use(content: list) -> list:
        tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
        if len(tool_uses) <= 1:
            return content
        first_tool_id = tool_uses[0]["id"]
        filtered = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                if block["id"] == first_tool_id:
                    filtered.append(block)
            else:
                filtered.append(block)
        return filtered

    @staticmethod
    def _extract_single_tool_use(content: list) -> Optional[Dict[str, Any]]:
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return block
        return None

    @staticmethod
    def _check_flag_in_results(result: Dict[str, Any], flag_regex: str = r"flag\{[A-Za-z0-9_\-]+\}") -> bool:
        result_str = json.dumps(result, ensure_ascii=False)
        return bool(re.search(flag_regex, result_str, re.IGNORECASE))

    async def _consult_advisor(self, task: str, run_log: str) -> Optional[str]:
        if not self.memory:
            return None
        self._advisor_called_count += 1
        summary = self.memory.get_working_memory_summary(max_recent_rounds=5)
        recent_failures = []
        for attempt in self.memory.state.failed_attempts[-5:]:
            recent_failures.append(f"  - {attempt['description']} => {attempt['reason']}")
        failures_text = "\n".join(recent_failures) if recent_failures else "  (no recorded failures)"
        successful_outputs_text = self._build_successful_outputs_text()
        advisor_prompt = build_advisor_prompt(
            task=task,
            summary=summary,
            failures_text=failures_text,
            successful_outputs=successful_outputs_text,
        )
        try:
            # 修改点 1：使用自适应发送消息
            advisor_resp = await self._create_message_adaptive(
                messages=[{"role": "user", "content": advisor_prompt}],
                tools=None,
                max_tokens=800,
                effort="high"
            )
            advice_parts = []
            for block in advisor_resp.get("content", []):
                if block.get("type") == "text":
                    advice_parts.append(block.get("text", ""))
            advice = "\n".join(advice_parts).strip()
            self._log_jsonl(run_log, {
                "event": "advisor_consultation",
                "advice": advice,
                "advisor_call_count": self._advisor_called_count,
                "successful_findings_count": len(self.successful_findings),
            })
            return advice
        except Exception as e:
            self._log_jsonl(run_log, {"event": "advisor_error", "error": str(e)})
            return None

    def _record_successful_finding(self, round_idx: int, tool_name: str,
                                    tool_input: Dict[str, Any],
                                    result: Dict[str, Any]) -> None:
        output_summary = ""
        for key in ("stdout", "output", "mcp_output", "body"):
            val = result.get(key, "")
            if isinstance(val, str) and len(val.strip()) > 10:
                output_summary = val.strip()[:500]
                break
        if not output_summary:
            output_summary = json.dumps(result, ensure_ascii=False)[:500]
        self.successful_findings.append({
            "round": round_idx,
            "command": f"{tool_name}({json.dumps(tool_input, ensure_ascii=False)[:150]})",
            "output": output_summary,
        })

    def _build_successful_outputs_text(self) -> str:
        if not self.successful_findings:
            return "No successful outputs recorded yet."
        lines = []
        for item in self.successful_findings[-15:]:
            lines.append(f"- [Round {item['round']}] `{item['command']}`")
            lines.append(f"  Output: {item['output'][:150]}")
        return "\n".join(lines)

    def _should_force_conclusion(self, round_idx: int) -> bool:
        return (len(self.successful_findings) >= SUCCESSFUL_FINDINGS_THRESHOLD
            or round_idx >= FORCE_CONCLUSION_ROUND)

    def _build_force_conclusion_message(self, round_idx: int) -> str:
        findings_summary = "\n".join(
            f"- Round {f['round']}: {f['command'][:100]}"
            for f in self.successful_findings[-10:]
        )
        return (
            f"[System] 你已经进行了 {round_idx} 轮分析，收集了 "
            f"{len(self.successful_findings)} 条有效数据。\n"
            f"请基于已有数据立即输出最终结论/报告，不要再执行任何工具。\n\n"
            f"已收集的数据摘要：\n{findings_summary}"
        )

    async def solve(
            self, task: str, resume_messages: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        run_log = self._new_run_log()
        system_context = WEB_SYSTEM_PROMPT

        playbook_text = self.playbook_router.match_and_format(task)
        if playbook_text:
            matched_names = [m["name"] for m in self.playbook_router.match(task)]
            print(f"    [Playbook] 已匹配并加载: {', '.join(matched_names)}")
            system_context += f"\n\n{playbook_text}"

        if self.memory:
            memory_summary = self.memory.get_working_memory_summary()
            system_context += f"\n\n=== Task Memory ===\n{memory_summary}\n"

        if resume_messages:
            messages = [
                {
                    "role": "user",
                    "content": f"{system_context}\n\n[Task Resumed - Target URL might have been updated. Use the new URL below!]:\n{task}"
                }
            ]
            messages.extend(resume_messages)
        else:
            messages = [{"role": "user", "content": f"{system_context}\n\nTask:\n{task}"}]

        tools_def = self.tools.anthropic_tools()
        mcp_sessions: Dict[str, ClientSession] = {}

        async with AsyncExitStack() as stack:
            if self.mcp_configs:
                for config in self.mcp_configs:
                    read, write = await stack.enter_async_context(stdio_client(config))
                    session = await stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    mcp_tools = await session.list_tools()
                    for t in mcp_tools.tools:
                        tools_def.append({
                            "name": t.name,
                            "description": t.description,
                            "input_schema": t.inputSchema
                        })
                        mcp_sessions[t.name] = session

            matched_playbooks = [m["name"] for m in self.playbook_router.match(task)]
            self._log_jsonl(run_log, {
                "event": "start",
                "task": task,
                "matched_playbooks": matched_playbooks,
            })

            for round_idx in range(1, self.max_rounds + 1):
                effort = "high" if round_idx <= 8 else "max"

                if self._should_force_conclusion(round_idx):
                    last_msg = messages[-1] if messages else {}
                    last_content = last_msg.get("content", "")
                    if isinstance(last_content, str) and "[System] 你已经进行了" not in last_content:
                        force_msg = self._build_force_conclusion_message(round_idx)
                        messages.append({"role": "user", "content": force_msg})
                        self._log_jsonl(run_log, {
                            "event": "force_conclusion_injected",
                            "round": round_idx,
                            "successful_findings_count": len(self.successful_findings),
                        })

                windowed_messages = self._apply_sliding_window(messages)
                windowed_messages = self._inject_memory_update(windowed_messages)

                self._log_jsonl(run_log, {
                    "event": "llm_request",
                    "round": round_idx,
                    "effort": effort,
                    "message_count": len(windowed_messages),
                    "original_message_count": len(messages),
                })

                # 修改点 2：使用自适应的客户端请求
                resp = await self._create_message_adaptive(
                    messages=windowed_messages,
                    tools=tools_def,
                    max_tokens=1400,
                    effort=effort
                )

                stop_reason = resp.get("stop_reason")
                content = resp.get("content", [])

                self._log_jsonl(run_log, {
                    "event": "llm_response",
                    "round": round_idx,
                    "stop_reason": stop_reason,
                    "content": content,
                })

                if self.memory:
                    self.memory.add_round(round_idx, {"effort": effort}, resp)

                content = self._enforce_single_tool_use(content)
                tool_call = self._extract_single_tool_use(content)

                if tool_call is None:
                    messages.append({"role": "assistant", "content": content})
                    text_parts = []
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "text":
                            text_parts.append(b.get("text", ""))
                    final_text = "\n".join(text_parts).strip()
                    if final_text:
                        self._log_jsonl(run_log, {"event": "final_text", "round": round_idx, "text": final_text})
                        if self.memory:
                            self.memory.mark_completed(True, final_text)
                        return {
                            "ok": True,
                            "rounds": round_idx,
                            "response": final_text,
                            "run_log": run_log,
                            "messages": messages,
                            "raw": resp,
                            "advisor_calls": self._advisor_called_count,
                        }
                    continue

                messages.append({"role": "assistant", "content": content})
                tool_name = tool_call["name"]
                tool_use_id = tool_call["id"]
                tool_input = tool_call.get("input", {})

                if tool_name in mcp_sessions:
                    try:
                        mcp_result = await mcp_sessions[tool_name].call_tool(tool_name, arguments=tool_input)
                        res_text = "\n".join([c.text for c in mcp_result.content if c.type == "text"])
                        result = {"ok": True, "mcp_output": res_text}
                    except Exception as e:
                        result = {"ok": False, "error": str(e)}
                else:
                    result = self.tools.call(tool_name, tool_input)

                is_error = not result.get("ok", False)
                self._log_jsonl(run_log, {
                    "event": "tool_result",
                    "round": round_idx,
                    "tool_name": tool_name,
                    "tool_use_id": tool_use_id,
                    "tool_input": tool_input,
                    "result": result,
                    "is_error": is_error,
                })

                if self.memory:
                    self.memory.add_tool_result(round_idx, tool_name, tool_input, result)

                if is_error:
                    if self.memory:
                        self.memory.add_failed_attempt(
                            f"{tool_name}({json.dumps(tool_input)[:100]})",
                            result.get("error", "unknown"),
                        )
                else:
                    self._record_successful_finding(round_idx, tool_name, tool_input, result)

                tool_result_msg: List[Dict[str, Any]] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                ]
                messages.append({"role": "user", "content": tool_result_msg})

                if round_idx % ADVISOR_INTERVAL == 0:
                    print(f"    [Advisor] Scheduled advisor check at round {round_idx}...")
                    advice = await self._consult_advisor(task, run_log)
                    if advice:
                        if self.memory:
                            self.memory.add_human_hint(f"[Advisor #{self._advisor_called_count}]: {advice[:300]}")
                        if self._should_force_conclusion(round_idx):
                            advisor_msg = (
                                f"[System] 顾问建议如下，但你已收集了足够数据。"
                                f"请在下一轮直接输出结论，不要再执行工具。\n\n"
                                f"顾问建议：{advice}"
                            )
                        else:
                            advisor_msg = f"[Advisor] {advice}"
                        messages.append({"role": "user", "content": advisor_msg})
                        self._log_jsonl(run_log, {
                            "event": "advisor_injected",
                            "round": round_idx,
                            "force_conclusion": self._should_force_conclusion(round_idx),
                        })

                flag_regex = os.getenv("CTF_FLAG_REGEX", r"flag\{[A-Za-z0-9_\-]+\}")
                if self._check_flag_in_results(result, flag_regex):
                    self._log_jsonl(run_log, {
                        "event": "flag_candidate_detected",
                        "round": round_idx,
                        "tool_name": tool_name,
                    })

                self._log_jsonl(run_log, {
                    "event": "round_complete",
                    "round": round_idx,
                    "tool": tool_name,
                    "success": not is_error,
                    "total_findings": len(self.successful_findings),
                })

            if self.memory:
                self.memory.mark_completed(False, f"max rounds exceeded ({self.max_rounds})")

            return {
                "ok": False,
                "error": f"max rounds exceeded ({self.max_rounds})",
                "run_log": run_log,
                "messages": messages,
                "advisor_calls": self._advisor_called_count,
            }