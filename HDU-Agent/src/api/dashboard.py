# src/api/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List
from src.core.database import get_db
from src.core import models, schemas
from src.core.security import get_current_user  # 假设你用这个获取当前用户

router = APIRouter()

@router.get("/stats", response_model=schemas.DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_user) # 如果需要做用户权限隔离则开启
):
    # 1. 计算今日日期范围
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 2. 真实数据查询
    # -- 统计今日漏洞数 --
    vulns_today = db.query(models.Vulnerability).filter(
        models.Vulnerability.created_at >= today_start
    ).count()

    # -- 统计活跃 Agent 数 (查询最近10分钟内处于 running 状态或有更新的任务) --
    ten_mins_ago = datetime.now() - timedelta(minutes=10)
    active_agents = db.query(models.Task).filter(
        models.Task.updated_at >= ten_mins_ago,
        models.Task.status == "running"
    ).count()

    # -- 漏洞等级分布图真实查询逻辑 --
    severity_counts = db.query(
        models.Vulnerability.severity, 
        func.count(models.Vulnerability.id)
    ).group_by(models.Vulnerability.severity).all()
    
    vuln_map = { "critical": "致命 (Critical)", "high": "高危 (High)", "medium": "中危 (Medium)", "low": "低危 (Low)" }
    
    # 将查询结果转换为字典以便处理
    sev_dict = {sev: count for sev, count in severity_counts}
    
    # 构造前端图表所需数据（即使某类漏洞为0，也返回0以保持图表完整）
    vuln_distribution = [
        {"name": vuln_map["critical"], "value": sev_dict.get("critical", 0)},
        {"name": vuln_map["high"], "value": sev_dict.get("high", 0)},
        {"name": vuln_map["medium"], "value": sev_dict.get("medium", 0)},
        {"name": vuln_map["low"], "value": sev_dict.get("low", 0)}
    ]

    # 3. 动态计算安全分数 (基础分100)
    # 扣分规则：致命-20，高危-10，中危-3，低危-1
    deduction = (
        sev_dict.get("critical", 0) * 20 +
        sev_dict.get("high", 0) * 10 +
        sev_dict.get("medium", 0) * 3 +
        sev_dict.get("low", 0) * 1
    )
    # 分数限制在 0 - 100 之间
    security_score = max(0, 100 - deduction)

    # 4. 构造大盘 Summary
    summary = schemas.DashboardSummary(
        security_score=security_score,
        vulns_today=vulns_today,
        active_agents=active_agents,
        token_usage="128.5K" # 暂时保留占位，或接入 LLM API 调用量统计
    )

    # 5. 自动化攻击链路图 (目前暂时保留结构化的静态数据，后续第四步对接 Agent Manager)
    attack_graph = schemas.AttackGraph(
        nodes=[
            {"id": "A", "name": "外网入口 IP\n(203.0.113.5)", "category": 0},
            {"id": "B", "name": "Web服务\n(80端口)", "category": 1},
            {"id": "C", "name": "SQL注入发现\n(login.php)", "category": 2},
            {"id": "D", "name": "获取 WebShell", "category": 3},
            {"id": "E", "name": "内网横向移动\n(10.0.0.5)", "category": 3}
        ],
        edges=[
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
            {"source": "C", "target": "D"},
            {"source": "D", "target": "E"}
        ]
    )

    return schemas.DashboardStatsResponse(
        summary=summary,
        vuln_distribution=vuln_distribution,
        attack_graph=attack_graph
    )

@router.get("/vulnerabilities", response_model=List[schemas.VulnReportItem])
def get_all_vulnerabilities(db: Session = Depends(get_db)):
    """获取所有用户的漏洞扫描结果"""
    # 联合查询 Vulnerability -> Task -> User
    vulns = db.query(models.Vulnerability)\
        .join(models.Task, models.Vulnerability.task_id == models.Task.id)\
        .join(models.User, models.Task.user_id == models.User.id)\
        .order_by(models.Vulnerability.created_at.desc())\
        .all()
    
    result = []
    for v in vulns:
        result.append({
            "id": v.id,
            "vuln_name": v.vuln_name,
            "severity": v.severity,
            "description": v.description,
            "created_at": v.created_at,
            "target": v.task.target,
            "username": v.task.owner.username # 通过 relationship 获取关联用户名
        })
        
    return result
