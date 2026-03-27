"""Baseline Routes: /baseline"""

import os
from fastapi import APIRouter, HTTPException

from api.schemas import BaselineResponse

router = APIRouter()


@router.post("/baseline", response_model=BaselineResponse)
async def run_baseline():
    """
    Run baseline inference agent on all 3 tasks and return scores.

    This endpoint runs a HuggingFace-powered baseline agent on each task
    and returns the scores achieved.

    Requires HF_TOKEN environment variable for HuggingFace API access.
    """
    # Check for HuggingFace token
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise HTTPException(
            status_code=503,
            detail="HF_TOKEN environment variable not set. Cannot run baseline."
        )

    try:
        from baseline.inference import BaselineAgent

        agent = BaselineAgent(hf_token=hf_token)
        results = agent.run_all_tasks()

        return BaselineResponse(
            task_1_score=results["task_1_score"],
            task_2_score=results["task_2_score"],
            task_3_score=results["task_3_score"],
            average=results["average"],
            details=results.get("details", {}),
        )

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Baseline agent module not available."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Baseline agent failed: {str(e)}"
        )


@router.get("/baseline/status")
async def baseline_status():
    """Check if baseline agent is available and configured."""
    hf_token = os.environ.get("HF_TOKEN")

    status = {
        "hf_token_configured": hf_token is not None,
        "baseline_module_available": False,
    }

    try:
        from baseline.inference import BaselineAgent
        status["baseline_module_available"] = True
    except ImportError:
        pass

    status["ready"] = status["hf_token_configured"] and status["baseline_module_available"]

    return status
