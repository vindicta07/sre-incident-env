"""Scenario generators for SRE Incident Environment"""

from .base import BaseScenario, ScenarioConfig
from .easy import SingleServiceCrashScenario
from .medium import DatabaseCascadeScenario
from .hard import DistributedGhostScenario

__all__ = [
    "BaseScenario",
    "ScenarioConfig",
    "SingleServiceCrashScenario",
    "DatabaseCascadeScenario",
    "DistributedGhostScenario",
]

SCENARIO_REGISTRY = {
    "task_1_single_service_crash": SingleServiceCrashScenario,
    "task_2_db_cascade_failure": DatabaseCascadeScenario,
    "task_3_distributed_ghost_incident": DistributedGhostScenario,
}


def get_scenario(task_id: str) -> BaseScenario:
    """Get scenario instance by task ID"""
    if task_id not in SCENARIO_REGISTRY:
        raise ValueError(f"Unknown task_id: {task_id}. Available: {list(SCENARIO_REGISTRY.keys())}")
    return SCENARIO_REGISTRY[task_id]()
