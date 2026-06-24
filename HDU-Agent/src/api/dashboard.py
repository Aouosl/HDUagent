# src/api/dashboard.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.core.database import get_db
from src.core import models, schemas

router = APIRouter()


def _format_token_count(count: int) -> str:
    """格式化 token 数量为可读字符串"""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


@router.get("/stats", response_model=schemas.DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """获取仪表盘统计数据"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. 今日漏洞数
    vulns_today = db.query(models.Vulnerability).filter(
        models.Vulnerability.created_at >= today_start
    ).count()

    # 2. 活跃 Agent 数（最近10分钟处于 running 状态的任务）
    ten_mins_ago = now - timedelta(minutes=10)
    active_agents = db.query(models.Task).filter(
        models.Task.updated_at >= ten_mins_ago,
        models.Task.status == "running"
    ).count()

    # 3. 漏洞等级分布
    severity_counts = db.query(
        models.Vulnerability.severity,
        func.count(models.Vulnerability.id)
    ).group_by(models.Vulnerability.severity).all()

    vuln_map = {
        "critical": "致命 (Critical)", "high": "高危 (High)",
        "medium": "中危 (Medium)", "low": "低危 (Low)"
    }
    sev_dict = {sev: count for sev, count in severity_counts}

    vuln_distribution = [
        {"name": vuln_map["critical"], "value": sev_dict.get("critical", 0)},
        {"name": vuln_map["high"], "value": sev_dict.get("high", 0)},
        {"name": vuln_map["medium"], "value": sev_dict.get("medium", 0)},
        {"name": vuln_map["low"], "value": sev_dict.get("low", 0)}
    ]

    # 4. 动态安全分数（基础100，按漏洞严重程度扣分）
    deduction = (
        sev_dict.get("critical", 0) * 20 +
        sev_dict.get("high", 0) * 10 +
        sev_dict.get("medium", 0) * 3 +
        sev_dict.get("low", 0) * 1
    )
    security_score = max(0, 100 - deduction)

    # 5. Token 使用量（从 tasks 表汇总）
    total_tokens = db.query(func.coalesce(func.sum(models.Task.token_consumption), 0)).scalar()

    # 6. 汇总
    summary = schemas.DashboardSummary(
        security_score=security_score,
        vulns_today=vulns_today,
        active_agents=active_agents,
        token_usage=_format_token_count(total_tokens)
    )

    # 7. 攻击链路图（从最近完成的任务中获取）
    latest_task = db.query(models.Task).filter(
        models.Task.attack_graph_data.isnot(None)
    ).order_by(models.Task.updated_at.desc()).first()

    if latest_task and latest_task.attack_graph_data:
        graph_data = latest_task.attack_graph_data
        attack_graph = schemas.AttackGraph(
            nodes=graph_data.get("nodes", []),
            edges=graph_data.get("edges", [])
        )
    else:
        attack_graph = schemas.AttackGraph(nodes=[], edges=[])

    return schemas.DashboardStatsResponse(
        summary=summary,
        vuln_distribution=vuln_distribution,
        attack_graph=attack_graph
    )


@router.get("/vulnerabilities", response_model=schemas.VulnReportPaginatedResponse)
def get_all_vulnerabilities(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大100"),
    severity: Optional[str] = Query(None, description="按严重等级筛选：critical/high/medium/low"),
):
    """获取所有用户的漏洞扫描结果（分页）"""
    base_query = db.query(models.Vulnerability)\
        .join(models.Task, models.Vulnerability.task_id == models.Task.id)\
        .join(models.User, models.Task.user_id == models.User.id)

    if severity:
        base_query = base_query.filter(models.Vulnerability.severity == severity)

    total = base_query.count()

    vulns = base_query\
        .order_by(models.Vulnerability.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    items = [
        {
            "id": v.id,
            "vuln_name": v.vuln_name,
            "severity": v.severity,
            "description": v.description,
            "created_at": v.created_at,
            "target": v.task.target,
            "username": v.task.owner.username
        }
        for v in vulns
    ]

    return schemas.VulnReportPaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )

@router.get("/public/stats")
def get_public_stats(db: Session = Depends(get_db)):
    """公开统计数据（无需认证，用于 Landing 页面）"""
    total_vulns = db.query(func.count(models.Vulnerability.id)).scalar() or 0
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    active_agents = db.query(func.count(models.Task.id)).filter(
        models.Task.status == "running"
    ).scalar() or 0
    return {
        "total_vulnerabilities": total_vulns,
        "active_users": total_users,
        "active_agents": active_agents
    }
