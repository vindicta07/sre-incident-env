"""Environment Routes: /reset, /step, /state"""

import uuid
from fastapi import APIRouter, HTTPException

from environment import SREIncidentEnv
from environment.models import SREAction, ActionType
from api.schemas import ResetRequest, StepRequest, StepResponse

router = APIRouter()

# In-memory session storage (use Redis/DB in production)
_sessions: dict[str, SREIncidentEnv] = {}


def get_or_create_session(session_id: str | None) -> tuple[str, SREIncidentEnv]:
    """Get existing session or create a new one"""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())
    env = SREIncidentEnv()
    _sessions[new_id] = env
    return new_id, env


@router.post("/reset")
async def reset_environment(request: ResetRequest = None):
    """
    Start a new episode.

    Returns the initial observation for the selected (or random) task.
    """
    if request is None:
        request = ResetRequest()

    session_id, env = get_or_create_session(request.session_id)

    try:
        observation = env.reset(task_id=request.task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "session_id": session_id,
        "observation": observation.model_dump(),
        "task_id": env.scenario.task_id if env.scenario else None,
    }


@router.post("/step", response_model=StepResponse)
async def take_step(request: StepRequest):
    """
    Agent takes one action.

    Returns the new observation, reward, done flag, and info.
    """
    # Validate action type
    try:
        action_type = ActionType(request.action_type)
    except ValueError:
        valid_actions = [a.value for a in ActionType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type: {request.action_type}. Valid types: {valid_actions}"
        )

    # Get session
    if not request.session_id or request.session_id not in _sessions:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing session_id. Call /reset first to get a session."
        )

    env = _sessions[request.session_id]

    # Create action
    action = SREAction(
        action_type=action_type,
        target_service=request.target_service,
        parameters=request.parameters,
        reasoning=request.reasoning,
    )

    # Take step
    try:
        result = env.step(action)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StepResponse(
        observation=result.observation.model_dump(),
        reward=result.reward,
        done=result.done,
        info=result.info,
    )


@router.get("/state")
async def get_state(session_id: str):
    """
    Get current environment state without advancing.

    Requires a valid session_id from /reset.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id. Call /reset first."
        )

    env = _sessions[session_id]

    try:
        observation = env.state()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "session_id": session_id,
        "observation": observation.model_dump(),
        "done": env.done,
        "termination_reason": env.termination_reason,
    }


@router.get("/episode_history")
async def get_episode_history(session_id: str):
    """
    Get the complete episode history for grading.

    Requires a valid session_id from /reset.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id. Call /reset first."
        )

    env = _sessions[session_id]

    try:
        history = env.get_episode_history()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "session_id": session_id,
        "history": {
            "task_id": history.task_id,
            "total_steps": history.total_steps,
            "actions": [a.model_dump() for a in history.actions],
            "rewards": history.rewards,
            "final_state": history.final_state,
        }
    }
