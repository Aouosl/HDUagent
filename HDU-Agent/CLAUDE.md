# CLAUDE.md

## 项目概述

HDU-Agent 是一个基于 LangGraph 的多智能体自动化渗透测试系统。它利用大语言模型（LLM）作为调度核心，协调 7 个专业子智能体协同工作，覆盖从侦察到报告生成的完整攻击链。

## 技术栈

- **编排框架**: LangGraph (多智能体图编排)
- **LLM 集成**: LangChain (支持 OpenAI/DeepSeek/Qwen/Kimi/Zhipu/SiliconFlow)
- **Web 框架**: FastAPI + WebSocket
- **数据库**: PostgreSQL (via SQLAlchemy 2.0+)
- **认证**: JWT (python-jose)
- **CLI**: Python 命令行交互终端

## 项目结构

```
HDU-Agent/
├── main.py              # CLI 交互入口（开发调试用）
├── server.py            # FastAPI WebSocket 服务端
├── requirements.txt     # 依赖列表
├── .env                 # 环境变量（API Keys、数据库连接等）
└── src/
    ├── Agent/           # 多智能体系统核心
    │   ├── __init__.py          # 暴露 7 个子智能体构建函数
    │   ├── manager/             # 主图编排（Manager + Analyzer）
    │   │   ├── graph.py         # 主图构建与路由
    │   │   ├── nodes.py         # analyzer_node / manager_node
    │   │   ├── state.py         # AgentState / SubAgentInternalState
    │   │   ├── subagent_models.py
    │   │   └── subagent_factory.py
    │   └── subagent/            # 7 个专业子智能体
    │       ├── base.py          # 子智能体工厂（ReAct 循环）
    │       ├── recon_agent/     # 侦察（端口扫描、服务枚举、DNS 等）
    │       ├── web_agent/       # Web 安全（SQL注入/XSS/CSRF等）
    │       ├── exploit_agent/   # 漏洞利用
    │       ├── code_audit_agent/# 代码审计
    │       ├── binary_agent/    # 二进制安全（逆向、溢出、ROP）
    │       ├── internal_agent/  # 内网渗透（横向移动、域攻击）
    │       └── report_agent/    # 报告生成
    ├── api/              # REST API 路由
    │   ├── auth.py       # 认证
    │   ├── user.py       # 用户管理
    │   ├── agent_config.py
    │   ├── dashboard.py
    │   └── tasks.py
    ├── config/
    │   └── settings.py   # 全局配置（环境变量加载）
    ├── core/             # 核心基础设施
    │   ├── database.py   # SQLAlchemy 引擎与会话
    │   ├── models.py     # ORM 模型（User/ChatMessage/Task/Vulnerability...）
    │   ├── schemas.py    # Pydantic 请求/响应模式
    │   ├── llm_factory.py# LLM 实例工厂（多提供商支持）
    │   ├── security.py   # 密码哈希、JWT 验证
    │   ├── task_executor.py
    │   └── cleanup.py    # 定时数据清理
    ├── tools/            # 安全工具基类和注册
    │   ├── base.py       # BaseSecurityTool 基类
    │   ├── registery.py
    │   └── tool_registry.py
    └── fronted/          # 前端静态文件
```

## 架构：多智能体编排

```
                    analyzer（意图拆解 + 标签提取）
                        |
                    manager（调度决策）
                   /    |    |    |    |    \
            recon  web exploit code_audit binary internal report
                   \    |    |    |    |    /
                    manager（结果评估，继续/完成）
```

### 攻击链流水线
1. **recon_agent** → 侦察（端口扫描、服务枚举、DNS 发现）
2. **web_agent / code_audit_agent / binary_agent** → 漏洞发现
3. **exploit_agent** → 漏洞利用
4. **internal_agent** → 内网渗透（横向移动、提权）
5. **report_agent** → 报告生成

### 子智能体内部架构
每个子智能体遵循 ReAct 循环模式：
```
agent_node (LLM 决策) ⇄ tool_node (工具执行)
```
- `agent_node` 注入 system_prompt + 绑定工具 → LLM 决策
- `tool_node` 执行工具并返回结果
- 循环最多 `max_iterations=5` 次

### Manager 调度流程
1. Analyzer 分析用户意图 → 拆解复杂任务为步骤 + 提取技能标签
2. Manager 查看任务计划、子智能体结果、历史经验 → 做出 DispatchDecision
3. 条件路由到目标子智能体
4. 子智能体完成后返回 Manager 评估
5. 循环直到任务完成或直接回复用户

## 数据库核心表

| 表名 | 用途 |
|------|------|
| users | 用户账户、API Keys、画像数据 |
| agent_configs | 用户专属 Agent 配置 |
| chat_messages | 聊天消息历史（含直播日志） |
| agent_experiences | 子智能体经验记忆（成功率/失败率） |
| tasks | 任务记录（含攻击链路图） |
| vulnerabilities | 发现的漏洞资产 |

## 常用命令

```bash
# 启动 CLI 交互终端
python main.py

# 启动 Web 服务（FastAPI + WebSocket）
python server.py

# 初始化数据库表
python -m src.core.init_db
```

## LLM 提供商支持

Provider 注册表在 `src/core/llm_factory.py`:
- **openai** → 官方 OpenAI API
- **deepseek** → api.deepseek.com
- **qwen** → 阿里云 DashScope
- **kimi** → Moonshot API
- **zhipu** → 智谱 GLM API
- **silicon** → SiliconFlow API

优先级：用户前端传入的 Key > `.env` 全局环境变量

## 开发注意事项

1. **中文 Windows GBK 兼容**: `database.py` 中 monkey-patch psycopg2.connect 处理 GBK 编码异常
2. **消息上下文裁剪**: `manager_node` 保留 SystemMessage + 最近 15 条非系统消息
3. **上下文变量传递**: 使用 `contextvars` 在异步上下文中传递 `live_log_queue`、`event_loop`、`user_id`
4. **WebSocket 直播日志**: 批量写入数据库，每 2 秒或 50 条刷新一次
5. **频率限制**: 简易滑动窗口，60 秒窗口最多 120 请求（仅 API 路径）
6. **子智能体通过 `messages` 与父图共享状态**，通过 `subagent_results` 汇报结构化结果
