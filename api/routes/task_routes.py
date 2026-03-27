"""Task Routes: /tasks"""

from fastapi import APIRouter

from environment import SREIncidentEnv
from api.schemas import TaskListResponse

router = APIRouter()


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks():
    """
    List all available tasks with their descriptions and the action schema.
    """
    tasks = SREIncidentEnv.get_available_tasks()
    env = SREIncidentEnv()
    action_schema = env.get_action_schema()

    return TaskListResponse(
        tasks=tasks,
        action_schema=action_schema,
    )
