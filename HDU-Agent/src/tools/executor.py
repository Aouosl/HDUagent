# src/core/executor.py
import subprocess
import platform
from typing import Tuple


class CommandExecutor:
    """跨平台命令行工具执行器"""

    @staticmethod
    def run_cli(command: list[str], timeout: int = 300) -> Tuple[bool, str]:
        """
        执行命令行指令
        返回: (是否成功, 标准输出或错误信息)
        """
        try:
            # 针对 Windows 和 Linux 的差异化处理
            is_windows = platform.system().lower() == "windows"

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=is_windows  # Windows 下某些命令需要 shell=True
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, f"执行失败 (Exit code {result.returncode}): {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return False, f"错误：工具执行超时（超过 {timeout} 秒）"
        except FileNotFoundError:
            return False, f"错误：找不到可执行文件 {' '.join(command)}，请检查环境变量或路径。"
        except Exception as e:
            return False, f"发生未知系统错误: {str(e)}"