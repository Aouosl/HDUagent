# src/tools/security/dir_brute_tool.py
"""
目录爆破工具 — Web 目录/文件枚举

支持 gobuster 和 ffuf 两种后端，自动检测可用工具。
"""
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from src.tools.base import BaseSecurityTool
from src.tools.executor import CommandExecutor


class DirBruteArgs(BaseModel):
    """DirBruteTool 的参数模式"""
    url: str = Field(description="目标 URL（如 http://example.com）")
    wordlist: Optional[str] = Field(
        default=None,
        description="字典文件路径。留空使用内置 common.txt"
    )
    extensions: Optional[str] = Field(
        default=None,
        description="文件扩展名，逗号分隔（如 'php,html,js'）"
    )
    threads: int = Field(default=20, description="并发线程数")
    backend: Literal["auto", "gobuster", "ffuf"] = Field(
        default="auto",
        description="后端工具: auto=自动检测, gobuster, ffuf"
    )


class DirBruteTool(BaseSecurityTool):
    """Web 目录/文件爆破枚举工具"""

    name: str = "dir_brute"
    description: str = (
        "对目标 Web 应用进行目录和文件爆破枚举。"
        "自动检测并使用 gobuster 或 ffuf 作为后端。"
        "返回发现的路径及其 HTTP 状态码。"
    )
    args_schema: type[BaseModel] = DirBruteArgs

    def _run(
        self,
        url: str,
        wordlist: Optional[str] = None,
        extensions: Optional[str] = None,
        threads: int = 20,
        backend: str = "auto",
        **kwargs: Any,
    ) -> str:
        """执行目录爆破"""
        # 规范化 URL
        url = url.rstrip("/")

        tool_cmd = self._detect_backend(backend)
        if tool_cmd is None:
            return "错误: 未找到 gobuster 或 ffuf。请安装其中一个工具。"

        if tool_cmd == "gobuster":
            return self._run_gobuster(url, wordlist, extensions, threads)
        else:
            return self._run_ffuf(url, wordlist, extensions, threads)

    def _detect_backend(self, backend: str) -> Optional[str]:
        """检测可用的后端工具"""
        if backend == "gobuster":
            success, _ = CommandExecutor.run_cli(["gobuster", "--help"], timeout=10)
            return "gobuster" if success else None
        elif backend == "ffuf":
            success, _ = CommandExecutor.run_cli(["ffuf", "-h"], timeout=10)
            return "ffuf" if success else None
        else:  # auto
            success, _ = CommandExecutor.run_cli(["gobuster", "--help"], timeout=10)
            if success:
                return "gobuster"
            success, _ = CommandExecutor.run_cli(["ffuf", "-h"], timeout=10)
            if success:
                return "ffuf"
            return None

    def _run_gobuster(
        self,
        url: str,
        wordlist: Optional[str],
        extensions: Optional[str],
        threads: int,
    ) -> str:
        """使用 gobuster 执行爆破"""
        cmd = ["gobuster", "dir", "-u", url, "-t", str(threads), "--no-error"]

        if wordlist:
            cmd.extend(["-w", wordlist])
        else:
            cmd.extend(["-w", "/usr/share/wordlists/dirb/common.txt"])

        if extensions:
            cmd.extend(["-x", extensions])

        success, output = CommandExecutor.run_cli(cmd, timeout=300)

        if not success:
            return f"gobuster 执行失败: {output}"

        # 提取发现的路径
        lines = output.split("\n")
        found = [line.strip() for line in lines if line.strip() and "Status:" in line]
        if not found:
            return f"未发现任何目录/文件。\n原始输出:\n{output[:1000]}"

        return "发现的路径:\n" + "\n".join(found[:50])

    def _run_ffuf(
        self,
        url: str,
        wordlist: Optional[str],
        extensions: Optional[str],
        threads: int,
    ) -> str:
        """使用 ffuf 执行爆破"""
        # ffuf URL 中 FUZZ 占位符
        ffuf_url = f"{url}/FUZZ"
        cmd = ["ffuf", "-u", ffuf_url, "-t", str(threads)]

        if wordlist:
            cmd.extend(["-w", wordlist])
        else:
            cmd.extend(["-w", "/usr/share/wordlists/dirb/common.txt"])

        if extensions:
            cmd.extend(["-e", extensions])

        # 过滤响应码
        cmd.extend(["-mc", "200,201,202,203,204,301,302,307,401,403,405,500"])

        success, output = CommandExecutor.run_cli(cmd, timeout=300)

        if not success:
            return f"ffuf 执行失败: {output}"

        if not output.strip():
            return "未发现任何路径。"

        # 提取发现的路径
        lines = output.strip().split("\n")
        found = [line.strip() for line in lines if line.strip()]
        return "发现的路径:\n" + "\n".join(found[:50])

    async def _arun(self, **kwargs: Any) -> str:
        """异步执行"""
        return self._run(**kwargs)
