# src/tools/security/nmap_tool.py
"""
Nmap 扫描工具 — 端口扫描与服务识别

封装 nmap CLI，支持：
- 端口扫描（TCP SYN / TCP Connect）
- 服务版本检测
- OS 指纹识别
- NSE 脚本执行
"""
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from src.tools.base import BaseSecurityTool
from src.tools.executor import CommandExecutor


class NmapScanArgs(BaseModel):
    """NmapScanTool 的参数模式"""
    target: str = Field(description="目标 IP 地址、主机名或 CIDR 网段")
    ports: Optional[str] = Field(
        default=None,
        description="端口范围，如 '1-1000'、'80,443' 或 'top-100'。留空则扫描常用 1000 端口"
    )
    scan_type: Literal["syn", "connect", "version", "os", "quick"] = Field(
        default="syn",
        description="扫描类型: syn=SYN半开, connect=全连接, version=服务版本, os=OS指纹, quick=快速"
    )
    extra_args: Optional[str] = Field(
        default=None,
        description="额外 nmap 参数（如 '-A -T4'），会追加到命令末尾"
    )


class NmapScanTool(BaseSecurityTool):
    """Nmap 端口扫描与服务识别工具"""

    name: str = "nmap_scan"
    description: str = (
        "使用 Nmap 对目标进行端口扫描和服务识别。"
        "支持 SYN 半开扫描、TCP 全连接扫描、服务版本检测和 OS 指纹识别。"
        "返回开放的端口列表、运行的服务及版本信息。"
    )
    args_schema: type[BaseModel] = NmapScanArgs

    def _run(
        self,
        target: str,
        ports: Optional[str] = None,
        scan_type: str = "syn",
        extra_args: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """执行 Nmap 扫描"""
        cmd = ["nmap"]

        # 扫描类型 → nmap 参数
        if scan_type == "syn":
            cmd.extend(["-sS"])  # SYN stealth scan
        elif scan_type == "connect":
            cmd.extend(["-sT"])  # TCP connect scan
        elif scan_type == "version":
            cmd.extend(["-sV", "--version-intensity", "5"])
        elif scan_type == "os":
            cmd.extend(["-O", "--osscan-guess"])
        elif scan_type == "quick":
            cmd.extend(["-T4", "-F"])  # Fast scan, top ports

        # 端口范围
        if ports:
            cmd.extend(["-p", ports])

        # 额外参数
        if extra_args:
            cmd.append(extra_args)

        # 默认启用服务版本检测和服务信息（除非 quick 模式）
        if scan_type not in ("quick", "os"):
            cmd.append("-sV")

        # 输出选项
        cmd.extend(["-oX", "-"])  # XML 输出到 stdout
        cmd.append(target)

        success, output = CommandExecutor.run_cli(cmd, timeout=600)

        if not success:
            return f"Nmap 扫描失败: {output}"

        # 尝试从 XML 中提取关键信息
        return self._parse_nmap_xml(output)

    def _parse_nmap_xml(self, xml_output: str) -> str:
        """简单解析 Nmap XML 输出，提取端口和服务信息"""
        lines = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_output)

            for host in root.findall(".//host"):
                addr_elem = host.find(".//address[@addrtype='ipv4']")
                ip = addr_elem.get("addr", "unknown") if addr_elem is not None else "unknown"

                hostname_elem = host.find(".//hostname[@type='user']")
                hostname = hostname_elem.get("name", "") if hostname_elem is not None else ""

                header = f"Host: {ip}"
                if hostname:
                    header += f" ({hostname})"
                lines.append(header)

                for port in host.findall(".//port"):
                    port_id = port.get("portid", "?")
                    protocol = port.get("protocol", "?")
                    state_elem = port.find("state")
                    state = state_elem.get("state", "?") if state_elem is not None else "?"

                    if state != "open":
                        continue

                    service_elem = port.find("service")
                    service_name = service_elem.get("name", "?") if service_elem is not None else "?"
                    product = service_elem.get("product", "") if service_elem is not None else ""
                    version = service_elem.get("version", "") if service_elem is not None else ""

                    port_info = f"  {port_id}/{protocol} - {service_name}"
                    if product:
                        port_info += f" ({product}"
                        if version:
                            port_info += f" {version}"
                        port_info += ")"
                    lines.append(port_info)

                # OS 检测
                os_elem = host.find(".//osmatch[@accuracy]")
                if os_elem is not None:
                    os_name = os_elem.get("name", "")
                    os_accuracy = os_elem.get("accuracy", "")
                    if os_name:
                        lines.append(f"  OS: {os_name} (accuracy: {os_accuracy}%)")

            if not lines:
                lines.append("(无开放端口或无法解析结果)")
        except Exception:
            # XML 解析失败，返回原始输出摘要
            lines.append(xml_output[:2000])

        return "\n".join(lines)

    async def _arun(self, **kwargs: Any) -> str:
        """异步执行（委托同步实现）"""
        return self._run(**kwargs)
