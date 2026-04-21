# PCAP 流量分析 — 标准操作流程

## Phase 1: 文件确认与基础信息

```bash
# 1. 确认文件存在和类型
ls -la <pcap文件路径>
file <pcap文件路径>

# 2. 基础统计 — 这是最重要的第一步，给你全局视野
tshark -r <file> -q -z io,stat,0
tshark -r <file> -q -z conv,ip      # IP 会话统计
tshark -r <file> -q -z endpoints,ip  # 端点统计
```

**关键判断点：** 如果文件很小（<1MB），可能只有几个关键包，重点看内容。如果很大，先看统计再深入。

## Phase 2: 协议分布分析

```bash
# 3. 协议层次统计
tshark -r <file> -q -z io,phs

# 4. 端口分布
tshark -r <file> -T fields -e tcp.dstport | sort | uniq -c | sort -rn | head -20
tshark -r <file> -T fields -e udp.dstport | sort | uniq -c | sort -rn | head -20
```

**关键判断点：**
- 看到 HTTP (80/8080)、HTTPS (443)、DNS (53)、FTP (21)、Telnet (23)、SSH (22) 等协议，决定下一步分析方向
- 如果只有 TCP 但没有已知应用层协议，可能是自定义协议或加密流量
- **如果 `io,phs` 显示 `_ws.short` 或协议层很浅，说明包可能被截断，不要反复尝试应用层过滤**

## Phase 3: 应用层协议检查

根据 Phase 2 的结果选择性执行：

### 如果有 HTTP 流量：
```bash
tshark -r <file> -Y "http.request" -T fields -e http.host -e http.request.method -e http.request.uri | head -30
tshark -r <file> -Y "http.response" -T fields -e http.response.code -e http.content_type | head -20

# 提取 HTTP 对象
tshark -r <file> --export-objects http,/tmp/http_objects/
```

### 如果有 DNS 流量：
```bash
tshark -r <file> -Y "dns.qry.name" -T fields -e dns.qry.name | sort | uniq -c | sort -rn | head -20
```

### 如果有 FTP/Telnet（明文协议）：
```bash
tshark -r <file> -Y "ftp" -T fields -e ftp.request.command -e ftp.request.arg | head -20
tshark -r <file> -z follow,tcp,ascii,0  # 跟踪第一个 TCP 流
```

### 如果没有已知应用层协议：
```bash
# 查看原始 TCP 载荷
tshark -r <file> -Y "tcp.payload" -T fields -e tcp.payload | head -10
# 检查是否有 TLS
tshark -r <file> -Y "tls" -T fields -e tls.handshake.type -e tls.record.version | head -10
```

**⚠️ 重要提示：如果某个过滤器返回空结果，这本身就是一个发现。**
- `http.request` 返回空 → "流量中不包含 HTTP 请求"是结论，不是需要重试的错误
- 不要对同一个返回空的过滤器重复执行 3 次以上

## Phase 4: 异常检测

```bash
# 5. 检查可疑端口和连接模式
tshark -r <file> -Y "tcp.flags.syn==1 && tcp.flags.ack==0" -T fields -e ip.src -e tcp.dstport | sort | uniq -c | sort -rn | head -20

# 6. 大流量检测
tshark -r <file> -q -z conv,tcp | sort -k 10 -rn | head -10

# 7. 检查是否有明文敏感信息
tshark -r <file> -Y "tcp.payload" -T fields -e tcp.payload | xxd -r -p | strings | grep -iE "(password|flag|secret|token|key|admin)" | head -20
```

## Phase 5: 写结论

当你完成以上步骤后（部分步骤可能因流量类型不适用而跳过），你已经有足够的数据写结论了。

**结论必须包含：**
1. **流量概览**：总包数、时间范围、主要通信对
2. **协议分布**：发现了哪些协议，各占比多少
3. **关键发现**：异常行为、敏感信息、攻击痕迹
4. **风险评估**：严重程度和影响范围
5. **建议**：后续应对措施

**即使所有检查都是"正常"的，那也是一个有效结论——"流量分析未发现明显异常"。**

## 常见陷阱

| 陷阱 | 应对 |
|------|------|
| `_ws.short` 出现在协议层次中 | 包被截断，应用层过滤大概率返回空，改用原始载荷分析 |
| `http.request` 反复返回空 | 不是 HTTP 流量，转向其他协议。**不要重试超过 1 次** |
| tshark 输出太大 | 重定向到文件：`tshark ... > /tmp/output.txt 2>/dev/null`，再用 head/grep 提取 |
| pcap 文件损坏 | 用 `capinfos <file>` 检查，或尝试 `editcap -F pcap <input> <output>` 修复 |
