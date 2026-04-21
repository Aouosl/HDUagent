import os
import json
import requests
from typing import Any, Dict, List

BASE_URL = "http://newapi.200m.997555.xyz"
API_KEY = "
MODEL = "claude-opus-4-6-thinking"  # 如果报模型不存在，就换成你面板里的实际模型名

ENDPOINT = f"{BASE_URL.rstrip('/')}/v1/messages"

# New API 文档显示支持 Bearer，也可用 x-api-key（二选一即可）
HEADERS = {
    "Content-Type": "application/json",
    "anthropic-version": "2025-06-01",
    "Authorization": f"Bearer {API_KEY}",
    # "x-api-key": API_KEY,  # 如需改用 x-api-key，打开这一行并移除 Authorization
}

def post_messages(payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)
    print(f"\n[HTTP {r.status_code}]")
    try:
        data = r.json()
    except Exception:
        print(r.text[:1000])
        raise
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    r.raise_for_status()
    return data

def extract_text(content_blocks: List[Dict[str, Any]]) -> str:
    texts = []
    for b in content_blocks or []:
        if b.get("type") in ("text", "string"):  # 某些代理文档示例里会写 string
            t = b.get("text", "")
            if t:
                texts.append(t)
    return "\n".join(texts).strip()

def test_plain():
    print("\n==== TEST 1: plain message ====")
    payload = {
        "model": MODEL,
        "max_tokens": 128,
        "stream": False,
        "messages": [
            {"role": "user", "content": "Reply with only: pong"}
        ],
    }
    data = post_messages(payload)
    print("stop_reason =", data.get("stop_reason"))
    print("text =", extract_text(data.get("content", [])))

def test_adaptive_thinking():
    print("\n==== TEST 2: adaptive thinking ====")
    payload = {
        "model": MODEL,
        "max_tokens": 256,
        "stream": False,
        "thinking": {"type": "adaptive"},
        # Claude 4.6 推荐用 effort 控制思考深度
        "output_config": {"effort": "medium"},
        "messages": [
            {"role": "user", "content": "Compute 37 * 48 and give only the number."}
        ],
    }
    data = post_messages(payload)
    print("stop_reason =", data.get("stop_reason"))
    print("text =", extract_text(data.get("content", [])))

def test_tool_use_roundtrip():
    print("\n==== TEST 3: tool use roundtrip ====")

    tools = [
        {
            "name": "echo_tool",
            "description": "Echo back the input text exactly.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    ]

    # 第一步：让模型调用工具
    payload1 = {
        "model": MODEL,
        "max_tokens": 256,
        "stream": False,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "low"},
        "tools": tools,
        "messages": [
            {
                "role": "user",
                "content": "Please call echo_tool with text='ping' and then tell me the result."
            }
        ],
    }
    resp1 = post_messages(payload1)

    content1 = resp1.get("content", [])
    tool_use_block = None
    for b in content1:
        if b.get("type") == "tool_use":
            tool_use_block = b
            break

    if not tool_use_block:
        print("❌ No tool_use block returned. 可能是代理/模型未启用工具调用，或模型直接回答。")
        print("assistant text:", extract_text(content1))
        return

    tool_use_id = tool_use_block["id"]
    tool_name = tool_use_block["name"]
    tool_input = tool_use_block.get("input", {})
    print(f"tool_use -> name={tool_name}, id={tool_use_id}, input={tool_input}")

    # 本地执行工具（这里就是简单 echo）
    tool_output = {"echoed": tool_input.get("text", "")}

    # 第二步：把 tool_result 回传（注意 tool_result 紧跟工具调用后回传）
    # Anthropic 文档要求 tool_result 要放在 user 消息 content 的前面
    messages2 = [
        {"role": "user", "content": "Please call echo_tool with text='ping' and then tell me the result."},
        {"role": "assistant", "content": content1},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(tool_output, ensure_ascii=False),
                }
            ],
        },
    ]

    payload2 = {
        "model": MODEL,
        "max_tokens": 256,
        "stream": False,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "low"},
        "tools": tools,
        "messages": messages2,
    }
    resp2 = post_messages(payload2)
    print("final text =", extract_text(resp2.get("content", [])))

if __name__ == "__main__":
    # 逐个跑，便于定位是哪一关出问题
    test_plain()
    test_adaptive_thinking()
    test_tool_use_roundtrip()