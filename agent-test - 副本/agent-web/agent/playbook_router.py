"""
PlaybookRouter — 根据任务描述自动匹配并加载对应的分析 SOP（标准操作流程）。

用法：
    router = PlaybookRouter("./playbooks")
    matched = router.match(task_description)
    # matched 是一个列表，每项包含 playbook 名称和内容
    # 直接拼接到 system prompt 后面即可

扩展：
    在 playbooks/ 目录下新建 .md 文件，在 ROUTE_TABLE 里加一条路由即可。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlaybookRoute:
    """一条路由规则：正则模式 → playbook 文件名"""
    name: str                  # 路由名称，用于日志
    patterns: List[str]        # 正则表达式列表，任一匹配即命中
    playbook_file: str         # playbooks/ 目录下的文件名
    priority: int = 0          # 优先级，数字越大越优先（多匹配时排序用）


# ---------------------------------------------------------------------------
# 路由表 — 在这里添加新的任务类型
# ---------------------------------------------------------------------------

ROUTE_TABLE: List[PlaybookRoute] = [
    PlaybookRoute(
        name="pcap_analysis",
        patterns=[
            r"\.pcap\b",
            r"pcap",
            r"流量分析",
            r"抓包",
            r"tshark",
            r"wireshark",
            r"tcpdump",
            r"packet\s*capture",
            r"network\s*traffic",
            r"流量包",
        ],
        playbook_file="pcap_analysis.md",
        priority=10,
    ),
    PlaybookRoute(
        name="web_pentest",
        patterns=[
            r"web\s*(渗透|漏洞|安全|测试|pentest|vuln|exploit)",
            r"(xss|sqli|sql.?inject|ssti|ssrf|rce|lfi|rfi|csrf)",
            r"(网站|站点|web\s*app).*(测试|扫描|渗透|攻击)",
            r"http[s]?://",
            r"(burp|dirsearch|gobuster|nikto|sqlmap)",
        ],
        playbook_file="web_pentest.md",
        priority=10,
    ),
    PlaybookRoute(
        name="reverse_engineering",
        patterns=[
            r"逆向",
            r"reverse\s*engineer",
            r"\.(elf|exe|bin|so|dll)\b",
            r"(反编译|反汇编|disassembl)",
            r"(ida|ghidra|radare|gdb|objdump)",
            r"binary\s*(analysis|exploit)",
            r"pwn",
        ],
        playbook_file="reverse_engineering.md",
        priority=10,
    ),
    PlaybookRoute(
        name="crypto_analysis",
        patterns=[
            r"crypto",
            r"密码学",
            r"(加密|解密|encrypt|decrypt)",
            r"(rsa|aes|des|md5|sha\d|hash|hmac)",
            r"(密文|明文|cipher|plaintext)",
        ],
        playbook_file="crypto_analysis.md",
        priority=10,
    ),
    PlaybookRoute(
        name="forensics",
        patterns=[
            r"取证",
            r"forensic",
            r"(内存|memory)\s*(分析|dump|image)",
            r"(磁盘|disk)\s*(镜像|image|分析)",
            r"(volatility|autopsy|foremost|binwalk)",
            r"\.(img|dd|raw|vmdk|E01)\b",
        ],
        playbook_file="forensics.md",
        priority=10,
    ),
    PlaybookRoute(
        name="misc_stego",
        patterns=[
            r"(隐写|stegan)",
            r"\bmisc\b",
            r"\.(png|jpg|jpeg|bmp|gif|wav|mp3)\b",
            r"(png|jpg|jpeg|gif|bmp).*(藏|隐藏|hidden|flag|secret|嵌入|embed)",
            r"(藏|隐藏|hidden|secret|嵌入).*(png|jpg|jpeg|gif|bmp|图片|图像|image|音频|audio)",
            r"(exiftool|steghide|stegsolve|zsteg|binwalk)",
            r"(图片|图像|image).*(分析|隐藏|藏|秘密|flag)",
        ],
        playbook_file="misc_stego.md",
        priority=5,
    ),
]


class PlaybookRouter:
    """
    根据任务描述匹配 playbook，返回匹配到的 SOP 内容。
    支持多匹配——一个任务可能同时命中多个 playbook。
    """

    def __init__(self, playbooks_dir: str = "./playbooks"):
        self.playbooks_dir = Path(playbooks_dir).resolve()
        self.routes = ROUTE_TABLE
        # 缓存已加载的 playbook 内容
        self._cache: Dict[str, Optional[str]] = {}

    def match(self, task_description: str) -> List[Dict[str, str]]:
        """
        扫描任务描述，返回所有匹配的 playbook。

        返回: [{"name": "pcap_analysis", "content": "...playbook内容..."}]
        按 priority 降序排列。
        """
        task_lower = task_description.lower()
        matched = []

        for route in self.routes:
            for pattern in route.patterns:
                if re.search(pattern, task_lower, re.IGNORECASE):
                    content = self._load_playbook(route.playbook_file)
                    if content:
                        matched.append({
                            "name": route.name,
                            "content": content,
                            "priority": route.priority,
                        })
                    break  # 一条路由只匹配一次

        # 按优先级排序
        matched.sort(key=lambda x: x["priority"], reverse=True)
        return matched

    def match_and_format(self, task_description: str) -> str:
        """
        匹配并格式化为可直接拼接到 system prompt 的文本。
        如果没有匹配返回空字符串。
        """
        matched = self.match(task_description)
        if not matched:
            return ""

        sections = []
        for m in matched:
            sections.append(
                f"\n{'=' * 60}\n"
                f"## Playbook: {m['name']}\n"
                f"以下是针对此类任务的标准操作流程（SOP），请严格按照步骤执行：\n"
                f"{'=' * 60}\n\n"
                f"{m['content']}"
            )

        return "\n".join(sections)

    def _load_playbook(self, filename: str) -> Optional[str]:
        """加载 playbook 文件内容，带缓存"""
        if filename in self._cache:
            return self._cache[filename]

        filepath = self.playbooks_dir / filename
        if not filepath.exists():
            self._cache[filename] = None
            return None

        try:
            content = filepath.read_text(encoding="utf-8").strip()
            self._cache[filename] = content
            return content
        except Exception:
            self._cache[filename] = None
            return None

    def list_available(self) -> List[str]:
        """列出所有可用的 playbook 文件"""
        if not self.playbooks_dir.exists():
            return []
        return [f.name for f in self.playbooks_dir.glob("*.md")]
