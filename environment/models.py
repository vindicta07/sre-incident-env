"""Pydantic models for SRE Incident Environment"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Alert severity levels"""
    P1 = "P1"  # Critical - immediate response required
    P2 = "P2"  # High - response within 30 minutes
    P3 = "P3"  # Medium - response within 4 hours
    P4 = "P4"  # Low - response within 24 hours


class LogLevel(str, Enum):
    """Log line severity levels"""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class ServiceStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ActionType(str, Enum):
    """Available SRE actions"""
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOY = "rollback_deploy"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RUN_SQL_QUERY = "run_sql_query"
    CHECK_LOGS = "check_logs"
    TOGGLE_FEATURE_FLAG = "toggle_feature_flag"
    ADD_CACHE_NODE = "add_cache_node"
    KILL_SLOW_QUERIES = "kill_slow_queries"
    ACKNOWLEDGE_ALERT = "acknowledge_alert"
    ESCALATE_TO_TEAM = "escalate_to_team"
    REVERT_CONFIG_CHANGE = "revert_config_change"
    FLUSH_CACHE = "flush_cache"
    NOOP = "noop"


class Alert(BaseModel):
    """PagerDuty-style alert"""
    service: str = Field(..., description="Service that triggered the alert")
    severity: Severity = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    fired_at: str = Field(..., description="ISO timestamp when alert fired")
    acknowledged: bool = Field(default=False, description="Whether alert has been acknowledged")


class ServiceMetrics(BaseModel):
    """Real-time metrics for a service"""
    cpu_pct: float = Field(..., ge=0, le=100, description="CPU utilization percentage")
    memory_pct: float = Field(..., ge=0, le=100, description="Memory utilization percentage")
    error_rate_pct: float = Field(..., ge=0, le=100, description="Error rate percentage")
    p99_latency_ms: float = Field(..., ge=0, description="99th percentile latency in ms")
    request_rate_rps: float = Field(..., ge=0, description="Requests per second")
    status: ServiceStatus = Field(..., description="Current service health status")


class LogLine(BaseModel):
    """Log entry from a service"""
    timestamp: str = Field(..., description="ISO timestamp")
    service: str = Field(..., description="Service that generated the log")
    level: LogLevel = Field(..., description="Log level")
    message: str = Field(..., description="Log message content")


class Deploy(BaseModel):
    """Deployment record"""
    service: str = Field(..., description="Service that was deployed")
    version: str = Field(..., description="Version string")
    deployed_at: str = Field(..., description="ISO timestamp of deployment")
    deployed_by: str = Field(..., description="User who triggered deployment")
    is_rollback_target: bool = Field(default=False, description="Whether this is a valid rollback target")


class SREObservation(BaseModel):
    """Complete observation state for the SRE agent"""
    incident_id: str = Field(..., description="Unique incident identifier")
    alerts: list[Alert] = Field(default_factory=list, description="Active alerts")
    metrics: dict[str, ServiceMetrics] = Field(default_factory=dict, description="Per-service metrics")
    logs: list[LogLine] = Field(default_factory=list, description="Recent log lines (last 50)")
    service_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Service dependency graph - key depends on values"
    )
    recent_deploys: list[Deploy] = Field(default_factory=list, description="Deploys in last 2 hours")
    step_count: int = Field(default=0, description="Current step number")
    elapsed_sim_minutes: int = Field(default=0, description="Simulated time since incident start")
    action_history: list[str] = Field(default_factory=list, description="Summary of past actions")


class SREAction(BaseModel):
    """Action taken by the SRE agent"""
    action_type: ActionType = Field(..., description="Type of action to take")
    target_service: str = Field(..., description="Service to act upon")
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional parameters for the action"
    )
    reasoning: str = Field(
        default="",
        description="Agent's explanation for taking this action"
    )


class SREReward(BaseModel):
    """Reward breakdown for an action"""
    total: float = Field(..., description="Total reward for this step")
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Individual reward components"
    )
    feedback: str = Field(default="", description="Human-readable feedback")


class StepResult(BaseModel):
    """Result of taking a step in the environment"""
    observation: SREObservation
    reward: float
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)


class EpisodeHistory(BaseModel):
    """Complete history of an episode for grading"""
    task_id: str
    actions: list[SREAction] = Field(default_factory=list)
    observations: list[SREObservation] = Field(default_factory=list)
    rewards: list[float] = Field(default_factory=list)
    total_steps: int = 0
    final_state: Optional[dict[str, Any]] = None


class TaskInfo(BaseModel):
    """Information about a task"""
    id: str
    name: str
    difficulty: str
    description: str
    target_score: str


class GraderResult(BaseModel):
    """Result from grading an episode"""
    score: float = Field(..., ge=0, le=1, description="Score from 0.0 to 1.0")
    breakdown: dict[str, Any] = Field(default_factory=dict)
    feedback: str = Field(default="")
