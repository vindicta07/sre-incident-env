"""Grader Routes: /grader"""

from fastapi import APIRouter, HTTPException

from environment.models import EpisodeHistory, SREAction, ActionType
from graders import grade_episode
from api.schemas import GraderRequest, GraderResponse

router = APIRouter()


@router.post("/grader", response_model=GraderResponse)
async def grade_episode_endpoint(request: GraderRequest):
    """
    Grade a completed episode.

    Accepts the task_id and episode_history, returns a score from 0.0 to 1.0
    with breakdown and feedback.
    """
    try:
        # Parse episode history
        history_data = request.episode_history

        # Convert actions to SREAction objects
        actions = []
        for action_dict in history_data.get("actions", []):
            try:
                action_type = ActionType(action_dict.get("action_type"))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid action_type in history: {action_dict.get('action_type')}"
                )

            actions.append(SREAction(
                action_type=action_type,
                target_service=action_dict.get("target_service", ""),
                parameters=action_dict.get("parameters"),
                reasoning=action_dict.get("reasoning", ""),
            ))

        # Create EpisodeHistory
        history = EpisodeHistory(
            task_id=request.task_id,
            actions=actions,
            rewards=history_data.get("rewards", []),
            total_steps=history_data.get("total_steps", len(actions)),
            final_state=history_data.get("final_state"),
        )

        # Grade the episode
        result = grade_episode(request.task_id, history)

        return GraderResponse(
            score=result.score,
            breakdown=result.breakdown,
            feedback=result.feedback,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
