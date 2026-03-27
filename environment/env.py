"""Main SRE Incident Environment

The core environment class implementing step(), reset(), state().
"""

import random
from typing import Any, Optional

from .models import (
    SREObservation,
    SREAction,
    SREReward,
    StepResult,
    EpisodeHistory,
    ActionType,
)
from .scenarios import get_scenario, SCENARIO_REGISTRY
from .scenarios.base import BaseScenario
from .simulator import ServiceSimulator
from .reward import RewardCalculator


class SREIncidentEnv:
    """
    SRE Incident Response Environment.

    Agent acts as an on-call SRE receiving production alerts.
    It must diagnose the root cause from noisy logs, metrics, and alerts,
    then take the correct remediation actions in the right order.
    """

    MAX_STEPS = 20

    def __init__(self):
        self.scenario: Optional[BaseScenario] = None
        self.simulator: Optional[ServiceSimulator] = None
        self.reward_calculator = RewardCalculator()
        self.current_observation: Optional[SREObservation] = None
        self.episode_history: Optional[EpisodeHistory] = None
        self.done = False
        self.termination_reason: Optional[str] = None

    def reset(self, task_id: Optional[str] = None) -> SREObservation:
        """
        Start a new episode.

        Args:
            task_id: Specific task to run. If None, random task is selected.

        Returns:
            Initial observation
        """
        # Select task
        if task_id is None:
            task_id = random.choice(list(SCENARIO_REGISTRY.keys()))

        # Initialize scenario and simulator
        self.scenario = get_scenario(task_id)
        self.simulator = ServiceSimulator(self.scenario)

        # Reset simulator and get initial observation
        self.current_observation = self.simulator.reset()

        # Initialize reward calculator
        initial_affected = self.simulator.get_affected_services_count()
        self.reward_calculator.reset(initial_affected)

        # Initialize episode history
        self.episode_history = EpisodeHistory(
            task_id=task_id,
            observations=[self.current_observation],
            actions=[],
            rewards=[],
            total_steps=0,
        )

        self.done = False
        self.termination_reason = None

        return self.current_observation

    def step(self, action: SREAction) -> StepResult:
        """
        Agent takes one action.

        Args:
            action: The action to take

        Returns:
            StepResult with observation, reward, done, info
        """
        if self.done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")

        if self.simulator is None or self.current_observation is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        # Apply action
        new_observation, effects = self.simulator.apply_action(
            action, self.current_observation
        )

        # Calculate reward
        scenario_config = {
            "root_cause_services": self.scenario.root_cause_services,
            "root_cause_description": self.scenario.config.root_cause_description,
            "services_affected": self.scenario.config.services_affected,
            "difficulty": self.scenario.config.difficulty,
        }
        reward_result = self.reward_calculator.calculate(
            action=action,
            effects=effects,
            step_count=self.simulator.step_count,
            scenario_config=scenario_config,
        )

        # Check termination conditions
        done = False
        termination_reason = None

        if effects.get("is_resolved"):
            done = True
            termination_reason = "incident_resolved"
        elif effects.get("catastrophic"):
            done = True
            termination_reason = "catastrophic_action_taken"
        elif self.simulator.step_count >= self.MAX_STEPS:
            done = True
            termination_reason = "max_steps_reached"

        self.done = done
        self.termination_reason = termination_reason
        self.current_observation = new_observation

        # Update episode history
        self.episode_history.actions.append(action)
        self.episode_history.observations.append(new_observation)
        self.episode_history.rewards.append(reward_result.total)
        self.episode_history.total_steps = self.simulator.step_count

        # Build info dict
        info = {
            "root_cause_identified": effects.get("root_cause_addressed", False),
            "services_resolved": len(effects.get("services_fixed", [])),
            "total_services_affected": len(self.scenario.config.services_affected),
            "termination_reason": termination_reason,
            "reward_breakdown": reward_result.breakdown,
            "reward_feedback": reward_result.feedback,
            "step_count": self.simulator.step_count,
            "elapsed_sim_minutes": self.simulator.elapsed_minutes,
        }

        return StepResult(
            observation=new_observation,
            reward=reward_result.total,
            done=done,
            info=info,
        )

    def state(self) -> SREObservation:
        """
        Get current environment state without advancing.

        Returns:
            Current observation
        """
        if self.current_observation is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        return self.current_observation

    def get_episode_history(self) -> EpisodeHistory:
        """Get the episode history for grading"""
        if self.episode_history is None:
            raise RuntimeError("No episode history. Call reset() first.")

        # Add final state
        if self.current_observation:
            self.episode_history.final_state = {
                "metrics": {k: v.model_dump() for k, v in self.current_observation.metrics.items()},
                "done": self.done,
                "termination_reason": self.termination_reason,
            }

        return self.episode_history

    def get_action_schema(self) -> dict[str, Any]:
        """Get the action schema for API documentation"""
        return {
            "action_type": {
                "type": "enum",
                "values": [a.value for a in ActionType],
                "description": "Type of SRE action to take",
            },
            "target_service": {
                "type": "string",
                "description": "Service to act upon",
            },
            "parameters": {
                "type": "object",
                "description": "Optional parameters (e.g., {'version': 'v1.2.0'} for rollback)",
                "required": False,
            },
            "reasoning": {
                "type": "string",
                "description": "Agent's explanation for the action (used for partial credit)",
            },
        }

    @staticmethod
    def get_available_tasks() -> list[dict[str, str]]:
        """Get list of available tasks"""
        tasks = []
        for task_id, scenario_cls in SCENARIO_REGISTRY.items():
            scenario = scenario_cls()
            tasks.append({
                "id": task_id,
                "name": scenario.config.name,
                "difficulty": scenario.config.difficulty,
                "description": scenario.config.description,
                "target_score": scenario.config.target_score,
            })
        return tasks
