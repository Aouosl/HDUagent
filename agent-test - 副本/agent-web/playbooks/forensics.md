# 数字取证 — 标准操作流程

## Phase 1: 文件识别与基础分析

```bash
# 1. 确认文件类型
file <evidence>
binwalk <evidence>        # 检查嵌入文件
foremost -i <evidence> -o /tmp/carved  # 文件雕复

# 2. 文件系统检查（如果是磁盘镜像）
fdisk -l <image>
mmls <image>              # Sleuthkit 分区表
fls -r <image>            # 列出文件
```

## Phase 2: 内存取证（如果是内存 dump）

```bash
# 使用 Volatility 2/3
# 1. 识别操作系统
vol.py -f <dump> imageinfo           # Vol2
vol -f <dump> windows.info           # Vol3

# 2. 进程列表
vol.py -f <dump> --profile=<profile> pslist
vol.py -f <dump> --profile=<profile> pstree

# 3. 网络连接
vol.py -f <dump> --profile=<profile> netscan

# 4. 命令行历史
vol.py -f <dump> --profile=<profile> cmdscan
vol.py -f <dump> --profile=<profile> consoles

# 5. 文件提取
vol.py -f <dump> --profile=<profile> filescan | grep -i "flag\|secret\|password"
vol.py -f <dump> --profile=<profile> dumpfiles -Q <offset> -D /tmp/

# 6. 注册表
vol.py -f <dump> --profile=<profile> hivelist
vol.py -f <dump> --profile=<profile> hashdump
```

## Phase 3: 磁盘取证

```bash
# 1. 挂载镜像
mkdir /tmp/mnt
mount -o ro,loop <image> /tmp/mnt

# 2. 检查关键位置
ls -la /tmp/mnt/home/
cat /tmp/mnt/etc/passwd
cat /tmp/mnt/etc/shadow
ls -la /tmp/mnt/root/
find /tmp/mnt -name "*.txt" -o -name "*.log" -o -name "flag*"

# 3. 检查删除的文件
fls -d <image>                       # 列出已删除文件
icat <image> <inode>                 # 恢复特定 inode

# 4. 时间线分析
fls -m "/" -r <image> > /tmp/body.txt
mactime -b /tmp/body.txt -d > /tmp/timeline.csv
```

## Phase 4: 日志分析

```bash
# 系统日志
cat /var/log/auth.log | grep -i "fail\|error\|root"
cat /var/log/syslog | tail -100

# Web 日志
cat access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
cat access.log | grep -iE "(admin|flag|cmd|exec|eval|union|select)"

# 浏览器历史
sqlite3 places.sqlite "SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT 50;"
```

## Phase 5: 写结论

**结论必须包含：**
1. **证据概述**：文件类型、大小、来源
2. **关键发现**：可疑进程、文件、网络连接
3. **时间线**：事件发生的时间顺序
4. **Flag**（如果找到）
5. **取证链完整性**：分析方法是否影响证据

## 常见陷阱

| 陷阱 | 应对 |
|------|------|
| Volatility profile 识别失败 | 尝试 `vol3` 的自动检测，或手动指定常见 profile |
| 镜像挂载失败 | 检查偏移量：`mount -o ro,loop,offset=<bytes>` |
| 文件被删除 | 使用 `foremost`/`scalpel` 文件雕复 |
| 加密卷 | 检查是否有 LUKS/BitLocker 头，寻找密钥 |
