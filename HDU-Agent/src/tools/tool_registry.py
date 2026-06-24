# src/tools/tool_registry.py
"""
工具领域分类注册表 - 按子智能体名称映射领域专属工具列表

每个领域子智能体拥有专属安全工具 + 通用 memory 工具。
工具实例在模块加载时创建，避免每次查询时重复实例化。
"""
from typing import Dict, List
from langchain_core.tools import BaseTool
from src.tools.registery import get_all_tools
from src.tools.memory_tool import UpdateAgentMemoryTool
from src.tools.security.nmap_tool import NmapScanTool
from src.tools.security.dir_brute_tool import DirBruteTool
from src.tools.security.exploit_tool import SearchsploitTool


# ==================== 领域工具映射 ====================
# 每个领域列出该智能体应绑定的工具。键为 agent_name，值为工具实例列表。
# 通用 memory 工具会追加到每个领域中。

DOMAIN_TOOLS: Dict[str, List[BaseTool]] = {
    "recon_agent": [
        NmapScanTool(),
        # TODO: DnsEnumTool, SubdomainBruteTool, WhoisTool,
        #       ServiceBannerTool, OsFingerprintTool
    ],
    "web_agent": [
        DirBruteTool(),
        # TODO: SqlmapTool, XssScannerTool, CsrfTesterTool,
        #       SsrfTesterTool, WebFingerprintTool, ApiSecurityTool
    ],
    "exploit_agent": [
        SearchsploitTool(),
        # TODO: MetasploitTool, MsfvenomTool,
        #       ExploitDbTool, PrivEscCheckerTool, PayloadGeneratorTool
    ],
    "code_audit_agent": [
        # TODO: StaticAnalysisTool, DependencyCheckTool, SecretScannerTool,
        #       SemgrepTool, CveMatcherTool, ConfigAuditTool
    ],
    "binary_agent": [
        # TODO: DisassemblerTool, DebuggerTool, ChecksecTool,
        #       RopGadgetTool, ShellcodeTool, UnpackerTool
    ],
    "internal_agent": [
        # TODO: MimikatzTool, BloodHoundTool, CrackMapExecTool,
        #       ImpacketTool, ResponderTool, LdapSearchTool
    ],
    "report_agent": [
        # 报告生成不需要额外工具，纯文本生成
    ],
    "pentest_agent": [
        NmapScanTool(),
        DirBruteTool(),
        SearchsploitTool(),
    ],
}

# 通用工具，所有智能体共享
_COMMON_TOOLS: List[BaseTool] = [
    UpdateAgentMemoryTool(),
]


def get_tools_for_agent(agent_name: str) -> List[BaseTool]:
    """
    获取指定智能体的专属工具列表。

    Args:
        agent_name: 子智能体名称（如 "recon_agent"）

    Returns:
        工具实例列表（领域工具 + 通用工具）
    """
    domain = DOMAIN_TOOLS.get(agent_name, [])
    return domain + _COMMON_TOOLS


def list_all_agent_tools() -> Dict[str, int]:
    """列出所有智能体及其工具数量"""
    return {
        name: len(get_tools_for_agent(name))
        for name in DOMAIN_TOOLS
    }
