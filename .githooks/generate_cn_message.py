#!/usr/bin/env python3
"""
分析 staged diff，生成结构化的中文 commit message 模板。

用于 prepare-commit-msg 钩子，帮助开发者编写清晰、可审计的中文提交信息。
输出格式：
    <类型>: <简短描述>

    **变更概览**
    - 新增: n 个文件
    - 修改: n 个文件
    - 删除: n 个文件

    **详细变更**
    - <文件路径>: <自动推断的变更描述>

    **审计备注**
    - [ ] 已审查变更逻辑
    - [ ] 已确认无敏感信息泄露
    - [ ] 已验证相关测试通过
"""

import subprocess
import sys
import re
from pathlib import Path
from collections import defaultdict


def run_git(*args: str) -> str:
    """执行 git 命令并返回 stdout"""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def get_staged_files() -> dict[str, list[str]]:
    """获取暂存区文件按状态分类"""
    status_map = defaultdict(list)
    status_text = run_git("diff", "--cached", "--name-status")

    if not status_text:
        return dict(status_map)

    for line in status_text.split("\n"):
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, filename = parts
            if status == "A":
                status_map["新增"].append(filename)
            elif status == "M":
                status_map["修改"].append(filename)
            elif status == "D":
                status_map["删除"].append(filename)
            elif status.startswith("R"):
                status_map["重命名"].append(filename)
            else:
                status_map["其他"].append(filename)

    return dict(status_map)


def get_diff_summary(filepath: str) -> str:
    """获取单个文件的 diff 摘要"""
    diff = run_git("diff", "--cached", "-U0", "--", filepath)
    if not diff:
        return ""

    lines = diff.split("\n")
    added_lines = 0
    removed_lines = 0
    added_functions: list[str] = []
    removed_functions: list[str] = []
    added_imports: list[str] = []
    removed_imports: list[str] = []
    added_classes: list[str] = []
    removed_classes: list[str] = []

    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
            # 检测新增的函数/方法
            m = re.search(r'^\+\s*(?:async\s+)?def\s+(\w+)', line)
            if m:
                added_functions.append(m.group(1))
            # 检测新增的 import
            m = re.search(r'^\+\s*(?:from\s+[\w.]+)?\s*import\s+(.+?)(?:\s+#.*)?$', line)
            if m:
                added_imports.append(m.group(1).strip())
            # 检测新增的类
            m = re.search(r'^\+\s*class\s+(\w+)', line)
            if m:
                added_classes.append(m.group(1))
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines += 1
            m = re.search(r'^-\s*(?:async\s+)?def\s+(\w+)', line)
            if m:
                removed_functions.append(m.group(1))
            m = re.search(r'^-\s*(?:from\s+[\w.]+)?\s*import\s+(.+?)(?:\s+#.*)?$', line)
            if m:
                removed_imports.append(m.group(1).strip())
            m = re.search(r'^-\s*class\s+(\w+)', line)
            if m:
                removed_classes.append(m.group(1))

    # 构建变更描述
    desc_parts = []
    if added_functions:
        desc_parts.append(f"新增函数: {', '.join(added_functions[:5])}")
    if removed_functions:
        desc_parts.append(f"移除函数: {', '.join(removed_functions[:5])}")
    if added_classes:
        desc_parts.append(f"新增类: {', '.join(added_classes[:3])}")
    if removed_classes:
        desc_parts.append(f"移除类: {', '.join(removed_classes[:3])}")
    if added_imports:
        desc_parts.append(f"新增导入: {', '.join(added_imports[:3])}")
    if removed_imports:
        desc_parts.append(f"移除导入: {', '.join(removed_imports[:3])}")

    change_detail = f"+{added_lines}/-{removed_lines}"
    if desc_parts:
        change_detail += " | " + " | ".join(desc_parts)

    return change_detail


def infer_commit_type(staged_files: dict[str, list[str]], all_files: list[str]) -> str:
    """根据变更内容推断 commit 类型"""
    all_changed = [f for sublist in staged_files.values() for f in sublist]

    # 检测文档变更
    doc_files = [f for f in all_changed if f.endswith((".md", ".rst", ".txt"))]
    if doc_files and len(doc_files) == len(all_changed):
        return "docs"

    # 检测测试变更
    test_files = [f for f in all_changed if "test" in Path(f).stem.lower()]
    if test_files and len(test_files) == len(all_changed):
        return "test"

    # 检测配置变更
    config_files = [f for f in all_changed if any(
        part in f for part in ["config", "settings", "docker", ".yml", ".yaml", ".json", ".toml", ".ini"]
    )]
    if config_files and len(config_files) == len(all_changed):
        return "chore"

    # 检测修复
    fix_keywords = ["fix", "bug", "修复", "issue", "error", "crash"]
    for f in all_changed:
        for kw in fix_keywords:
            if kw in Path(f).name.lower():
                return "fix"

    # 根据状态推断
    if "新增" in staged_files and len(staged_files.get("新增", [])) > len(staged_files.get("修改", [])):
        return "feat"
    if staged_files.get("修改"):
        return "refactor"

    return "chore"


def generate_message() -> str:
    """生成完整的中文 commit message 模板"""
    staged_files = get_staged_files()

    if not staged_files:
        return ""  # 没有暂存文件时不生成模板

    all_files = [f for sublist in staged_files.values() for f in sublist]

    # 推断提交类型
    commit_type = infer_commit_type(staged_files, all_files)

    # 统计
    added_count = len(staged_files.get("新增", []))
    modified_count = len(staged_files.get("修改", []))
    deleted_count = len(staged_files.get("删除", []))
    renamed_count = len(staged_files.get("重命名", []))
    other_count = len(staged_files.get("其他", []))

    total = added_count + modified_count + deleted_count + renamed_count + other_count
    if total == 0:
        return ""

    # 构建简短描述（需要用户填入）
    short_desc_map = {
        "feat":    "新增功能: <请简述变更内容>",
        "fix":     "修复问题: <请简述变更内容>",
        "refactor":"重构优化: <请简述变更内容>",
        "docs":    "文档更新: <请简述变更内容>",
        "test":    "测试变更: <请简述变更内容>",
        "chore":   "杂项维护: <请简述变更内容>",
    }
    short_desc = short_desc_map.get(commit_type, "变更: <请简述变更内容>")

    lines: list[str] = []
    lines.append(short_desc)
    lines.append("")

    # 变更概览
    lines.append("**变更概览**")
    if added_count:
        lines.append(f"- 新增: {added_count} 个文件")
    if modified_count:
        lines.append(f"- 修改: {modified_count} 个文件")
    if deleted_count:
        lines.append(f"- 删除: {deleted_count} 个文件")
    if renamed_count:
        lines.append(f"- 重命名: {renamed_count} 个文件")
    if other_count:
        lines.append(f"- 其他: {other_count} 个文件")
    lines.append("")

    # 详细变更
    lines.append("**详细变更**")
    all_statuses = ["新增", "修改", "删除", "重命名", "其他"]
    for status in all_statuses:
        files = staged_files.get(status, [])
        for f in files:
            summary = get_diff_summary(f) if status in ("新增", "修改") else status
            lines.append(f"- `{f}`: {summary}")

    lines.append("")

    # 审计备注
    lines.append("**审计备注**")
    lines.append("- [ ] 已审查变更逻辑")
    lines.append("- [ ] 已确认无敏感信息泄露")
    lines.append("- [ ] 已验证相关测试通过")

    return "\n".join(lines)


def main():
    # 强制 UTF-8 输出，解决 Windows 下中文乱码问题
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        msg = generate_message()
        if msg:
            print(msg)
    except Exception as e:
        # 钩子失败不应该阻止提交，静默退出
        print(f"# [Hook Warning] 生成中文模板失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
