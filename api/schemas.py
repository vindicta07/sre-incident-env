"""API Request/Response Schemas"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from environment.models import ActionType


class ResetRequest(BaseModel):
    """Request body for /reset endpoint"""
    task_id: Optional[str] = Field(
        default=None,
        description="Task ID to run. If omitted, random task is selected.",
        examples=["task_1_single_service_crash", "task_2_db_cascade_failure"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for state management"
    )


class StepRequest(BaseModel):
    """Request body for /step endpoint"""
    action_type: str = Field(
        ...,
        description="Type of action to take",
        examples=["rollback_deploy", "restart_service", "check_logs"]
    )
    target_service: str = Field(
        ...,
        description="Service to act upon",
        examples=["auth-service", "postgres-primary"]
    )
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional parameters for the action",
        examples=[{"version": "v2.3.0"}, {"replicas": 3}]
    )
    reasoning: str = Field(
        default="",
        description="Agent's explanation for taking this action"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for state management"
    )


class StepResponse(BaseModel):
    """Response body for /step endpoint"""
    observation: dict[str, Any]
    reward: float
    done: bool
    info: dict[str, Any]


class GraderRequest(BaseModel):
    """Request body for /grader endpoint"""
    task_id: str = Field(..., description="Task ID that was run")
    episode_history: dict[str, Any] = Field(
        ...,
        description="Complete episode history including actions, observations, rewards"
    )


class GraderResponse(BaseModel):
    """Response body for /grader endpoint"""
    score: float = Field(..., ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    breakdown: dict[str, Any] = Field(..., description="Score breakdown by component")
    feedback: str = Field(..., description="Human-readable feedback")


class BaselineResponse(BaseModel):
    """Response body for /baseline endpoint"""
    task_1_score: float
    task_2_score: float
    task_3_score: float
    average: float
    details: dict[str, Any] = Field(default_factory=dict)


class TaskListResponse(BaseModel):
    """Response body for /tasks endpoint"""
    tasks: list[dict[str, str]]
    action_schema: dict[str, Any]


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
