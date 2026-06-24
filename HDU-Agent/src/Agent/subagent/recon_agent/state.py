# src/Agent/subagent/recon_agent/state.py
"""
Recon Agent state definitions and Pydantic structured output models.

Following the manager agent pattern:
- Pydantic BaseModel classes for structured LLM outputs
- Shared with nodes.py for type-safe node implementations
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== Pydantic Structured Output Models ====================

class ReconFinding(BaseModel):
    """A single reconnaissance finding (asset, port, service, etc.)."""
    id: str = Field(description="Unique finding ID, e.g. F-001")
    category: str = Field(description="asset|port|service|os_fingerprint|vulnerability|info")
    severity: str = Field(description="Critical|High|Medium|Low|Info")
    title: str = Field(description="Short descriptive title")
    description: str = Field(description="Detailed description of the finding")
    evidence: str = Field(default="", description="Supporting evidence (banner, output snippet)")
    host: str = Field(default="", description="Target host (IP or domain)")
    port: Optional[int] = Field(default=None, description="Port number if applicable")
    service: str = Field(default="", description="Service name if identified")
    version: str = Field(default="", description="Service/OS version if identified")
    recommendation: str = Field(default="", description="Suggested next action")



class ExecutionStep(BaseModel):
    """A single step in the recon execution plan."""
    step_number: int = Field(description="1-indexed step number")
    phase: str = Field(description="Phase: passive|active|service|fingerprint|report")
    description: str = Field(description="What this step aims to achieve")
    tools_needed: List[str] = Field(default_factory=list, description="Tools expected for this step")
    expected_output: str = Field(description="Expected output from this step")
    dependencies: List[int] = Field(default_factory=list)


class ReconPlan(BaseModel):
    """Structured recon plan produced by the orchestrator."""
    agent_name: str = Field(default="recon_agent")
    task_summary: str = Field(description="One-line summary of the recon task")
    steps: List[ExecutionStep] = Field(description="Ordered execution steps (2-5)")
    success_criteria: str = Field(description="How to determine recon completion")
    risk_notes: str = Field(default="", description="Risk considerations (rate limiting, etc.)")


class StepEvaluation(BaseModel):
    """Evaluator output after a worker step."""
    step_completed: bool = Field(description="Whether step achieved its goal")
    quality_score: int = Field(description="1-10 quality rating")
    findings_extracted: List[ReconFinding] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    should_retry: bool = Field(description="Whether step needs retrying")
    retry_reason: str = Field(default="")
    should_continue: bool = Field(description="Whether to proceed to next step")
    abort_reason: str = Field(default="")


class ReconReport(BaseModel):
    """Final structured recon report."""
    agent_name: str = Field(default="recon_agent")
    status: str = Field(description="success|partial|failed")
    summary: str = Field(description="Executive summary of recon results")
    findings: List[ReconFinding] = Field(default_factory=list)
    steps_executed: int = Field(description="Steps actually executed")
    steps_total: int = Field(description="Total planned steps")
    key_insights: List[str] = Field(default_factory=list)
    next_recommendations: List[str] = Field(default_factory=list)
    errors_encountered: List[str] = Field(default_factory=list)
