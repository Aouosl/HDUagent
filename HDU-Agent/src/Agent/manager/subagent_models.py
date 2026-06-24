# src/Agent/manager/subagent_models.py
"""Pydantic structured output models for the LangGraph sub-agent architecture."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """A single step in the sub-agent execution plan."""
    step_number: int = Field(description="1-indexed step number")
    phase: str = Field(description="Phase: recon|scan|analyze|exploit|validate|report")
    description: str = Field(description="What this step aims to achieve")
    tools_needed: List[str] = Field(default_factory=list, description="Tools expected")
    expected_output: str = Field(description="What output this step should produce")
    dependencies: List[int] = Field(default_factory=list, description="Step numbers this depends on")


class SubAgentPlan(BaseModel):
    """Structured execution plan produced by the orchestrator node."""
    agent_name: str = Field(description="Sub-agent identifier")
    task_summary: str = Field(description="One-sentence task summary")
    steps: List[ExecutionStep] = Field(description="Ordered execution steps")
    success_criteria: str = Field(description="How to determine task completion")
    risk_notes: str = Field(default="", description="Risk considerations")


class Finding(BaseModel):
    """A single security finding."""
    id: str = Field(description="Unique finding ID e.g. F-001")
    category: str = Field(description="vulnerability|asset|configuration|info")
    severity: str = Field(description="Critical|High|Medium|Low|Info")
    title: str = Field(description="Short finding title")
    description: str = Field(description="Detailed description")
    evidence: str = Field(default="", description="Supporting evidence")
    cvss_score: Optional[float] = Field(default=None, description="CVSS 3.1 score")
    cve_id: Optional[str] = Field(default=None, description="CVE identifier")
    recommendation: str = Field(default="", description="Remediation recommendation")


class SubAgentReport(BaseModel):
    """Final structured report from sub-agent."""
    agent_name: str = Field(description="Sub-agent identifier")
    status: str = Field(description="success|partial|failed")
    summary: str = Field(description="Executive summary")
    findings: List[Finding] = Field(default_factory=list)
    steps_executed: int = Field(description="Steps actually executed")
    steps_total: int = Field(description="Total planned steps")
    key_insights: List[str] = Field(default_factory=list)
    next_recommendations: List[str] = Field(default_factory=list)
    errors_encountered: List[str] = Field(default_factory=list)


class StepEvaluation(BaseModel):
    """Evaluator node output after a worker step."""
    step_completed: bool = Field(description="Whether step achieved its goal")
    quality_score: int = Field(description="1-10 quality rating")
    findings_extracted: List[Finding] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    should_retry: bool = Field(description="Whether step needs retrying")
    retry_reason: str = Field(default="")
    should_continue: bool = Field(description="Whether to proceed to next step")
    abort_reason: str = Field(default="")
    next_step_adjustment: str = Field(default="")
