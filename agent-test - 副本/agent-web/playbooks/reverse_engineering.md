# 逆向工程 — 标准操作流程

## Phase 1: 文件识别

```bash
# 1. 基础信息
file <binary>
strings <binary> | head -50
strings <binary> | grep -iE "(flag|ctf|key|secret|password)"

# 2. 架构和格式
readelf -h <binary>        # ELF 文件头
readelf -S <binary>        # 段信息
readelf -s <binary>        # 符号表（可能被 strip）
```

**关键判断点：**
- ELF / PE / Mach-O → 对应 Linux/Windows/macOS 平台
- stripped → 没有符号信息，需要更多静态分析
- 是否有调试信息（DWARF）
- 是否是 PIE（位置无关可执行文件）

## Phase 2: 静态分析

```bash
# 3. 反汇编关键函数
objdump -d <binary> | head -200
objdump -d <binary> | grep -A 20 "<main>"

# 4. 检查导入/导出函数
readelf -d <binary>        # 动态段
nm <binary> 2>/dev/null    # 符号（如果没被 strip）

# 5. 检查安全特性
checksec --file=<binary>   # NX, ASLR, PIE, Canary, RELRO
```

### 如果是 Python 编译文件：
```bash
# .pyc 反编译
uncompyle6 <file>.pyc > decompiled.py
# 或
pycdc <file>.pyc
```

### 如果是 .NET 程序：
```bash
# 使用 dnSpy 或 ILSpy
monodis <file>.exe
```

### 如果是 Go 程序：
```bash
# Go 二进制通常很大且包含运行时
strings <binary> | grep "main\."
```

## Phase 3: 动态分析

```bash
# 6. 基础运行（在安全环境中）
chmod +x <binary>
ltrace ./<binary>     # 库调用追踪
strace ./<binary>     # 系统调用追踪

# 7. GDB 调试
gdb ./<binary>
# 常用命令：
# info functions     — 列出函数
# disas main         — 反汇编 main
# b *0x<addr>        — 设断点
# r                  — 运行
# x/20x $rsp         — 查看栈
# info registers     — 查看寄存器
```

## Phase 4: 常见 CTF 逆向模式

### 简单比较型：
```bash
# 找到比较逻辑，提取硬编码字符串
strings <binary> | grep -E "^.{10,50}$"  # 可能的 flag 长度
```

### 加密/编码型：
```bash
# 检查是否使用了已知加密库
strings <binary> | grep -iE "(aes|des|rc4|xor|base64|rot13)"
```

### 反调试型：
```bash
# 检查 ptrace 调用
objdump -d <binary> | grep ptrace
# 绕过：LD_PRELOAD 或 patch 二进制
```

## Phase 5: 写结论

**结论必须包含：**
1. **文件信息**：类型、架构、安全特性
2. **程序逻辑**：主要功能流程
3. **关键发现**：加密算法、验证逻辑、隐藏字符串
4. **Flag**（如果找到）
5. **分析方法**：使用了哪些工具和技术

## 常见陷阱

| 陷阱 | 应对 |
|------|------|
| stripped 二进制 | 用 `strings` + 交叉引用定位关键函数 |
| 反调试 | 用 `LD_PRELOAD` hook ptrace，或 patch 跳转指令 |
| 混淆 | 先运行观察行为，再针对性分析 |
| 大型二进制（Go/Rust） | 重点关注 `main` 和用户定义函数，忽略运行时 |
