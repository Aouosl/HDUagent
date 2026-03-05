import ast
import os
import sys
import subprocess
from pathlib import Path
from typing import Set, List, Dict
import importlib.metadata

# 忽略的目录（通常是虚拟环境、版本控制目录等）
IGNORE_DIRS = {'venv', 'env', '.venv', '.env', 'virtualenv',
               '__pycache__', '.git', '.svn', '.hg', 'build', 'dist'}


def get_stdlib_modules() -> Set[str]:
    """获取 Python 标准库模块名集合（Python 3.10+ 可使用 sys.stdlib_module_names，否则回退到粗略内置列表）"""
    if hasattr(sys, 'stdlib_module_names'):
        return set(sys.stdlib_module_names)
    else:
        # Python 3.10 之前没有 sys.stdlib_module_names，这里提供一个常见的内置模块列表（可扩展）
        return {
            'os', 'sys', 're', 'math', 'time', 'datetime', 'json', 'pickle',
            'random', 'itertools', 'functools', 'collections', 'pathlib',
            'subprocess', 'threading', 'multiprocessing', 'socket', 'http',
            'urllib', 'xml', 'csv', 'sqlite3', 'hashlib', 'hmac', 'base64',
            'tempfile', 'shutil', 'glob', 'fnmatch', 'argparse', 'logging',
            'unittest', 'doctest', 'inspect', 'traceback', 'warnings',
            'abc', 'io', 'struct', 'array', 'ctypes', 'curses', 'tty',
            'pty', 'turtle', 'tkinter', 'webbrowser', 'platform', 'getpass',
            'stat', 'fileinput', 'calendar', 'locale', 'gettext', 'codecs',
            'string', 're', 'difflib', 'textwrap', 'pprint', 'copy',
            'numbers', 'decimal', 'fractions', 'statistics', 'enum',
            'weakref', 'types', 'typing', 'dataclasses', 'contextlib',
            'importlib', 'pkgutil', 'runpy', 'zipfile', 'tarfile',
            'gzip', 'bz2', 'lzma', 'zlib', 'zipimport', 'cProfile',
            'profile', 'pstats', 'timeit', 'venv', 'ensurepip',
        }


def extract_imports_from_file(filepath: Path) -> Set[str]:
    """解析单个 Python 文件，提取顶级包名"""
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            # 忽略语法错误的文件（可能是不完整的文件）
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # 取顶级包名（如 import a.b.c -> a）
                top_level = alias.name.split('.')[0]
                imports.add(top_level)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                # from x.y import z -> 取 x
                top_level = node.module.split('.')[0]
                imports.add(top_level)
            # 忽略相对导入（node.level > 0），因为它们引用的是当前包内的模块
    return imports


def scan_project_imports(project_dir: str) -> Set[str]:
    """递归扫描项目目录，收集所有第三方模块的顶级包名"""
    stdlib = get_stdlib_modules()
    third_party_modules = set()
    root_path = Path(project_dir).resolve()

    for root, dirs, files in os.walk(root_path):
        # 跳过忽略目录
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                modules = extract_imports_from_file(filepath)
                for mod in modules:
                    # 过滤掉标准库、以 '_' 开头的（通常是内部模块）、以及当前项目内部的相对包（暂不处理）
                    if mod in stdlib or mod.startswith('_'):
                        continue
                    # 简单过滤：如果模块名是 Python 关键字或明显不是包名（如包含 '-'）则跳过
                    if not mod.isidentifier():
                        continue
                    third_party_modules.add(mod)

    return third_party_modules


def get_installed_packages() -> Dict[str, str]:
    """获取当前环境中所有已安装包及其版本号"""
    # 方法1：使用 importlib.metadata (Python 3.8+)
    packages = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata['Name']
        version = dist.version
        packages[name] = version
    return packages

    # 方法2：备选方案，使用 pip freeze（如果上面不可用）
    # try:
    #     result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'],
    #                              capture_output=True, text=True, check=True)
    #     lines = result.stdout.strip().split('\n')
    #     for line in lines:
    #         if '==' in line:
    #             name, version = line.split('==', 1)
    #             packages[name] = version
    # except Exception as e:
    #     print(f"运行 pip freeze 失败: {e}", file=sys.stderr)
    # return packages


def generate_requirements(modules: Set[str], output_file: str = 'requirements.txt'):
    """根据模块名集合生成 requirements.txt 文件，包含版本号"""
    installed = get_installed_packages()
    with open(output_file, 'w', encoding='utf-8') as f:
        for mod in sorted(modules):
            # 将模块名转换为小写（pip 包名通常不区分大小写，但规范使用小写）
            mod_lower = mod.lower()
            if mod_lower in installed:
                f.write(f"{mod_lower}=={installed[mod_lower]}\n")
            else:
                # 如果当前环境没有安装该包，只写模块名，不加版本
                f.write(f"{mod_lower}\n")
    print(f"✅ 已生成 {output_file}")


def main():
    # 默认扫描当前目录，也可以作为参数传入
    project_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f"🔍 正在扫描项目目录: {project_dir}")
    third_party_modules = scan_project_imports(project_dir)
    print(f"📦 发现第三方模块: {', '.join(sorted(third_party_modules))}")
    generate_requirements(third_party_modules)
    print("🎉 完成！")


if __name__ == '__main__':
    main()