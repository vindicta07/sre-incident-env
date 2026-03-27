"""Main Grader Dispatcher for SRE Incident Environment"""

from abc import ABC, abstractmethod
from typing import Any

from environment.models import EpisodeHistory, GraderResult, ActionType


class Grader(ABC):
    """Base class for task graders"""

    @abstractmethod
    def grade(self, history: EpisodeHistory) -> GraderResult:
        """
        Grade an episode.

        Args:
            history: Complete episode history

        Returns:
            GraderResult with score, breakdown, and feedback
        """
        pass

    def _count_action_types(self, history: EpisodeHistory) -> dict[str, int]:
        """Count occurrences of each action type"""
        counts = {}
        for action in history.actions:
            action_type = action.action_type.value
            counts[action_type] = counts.get(action_type, 0) + 1
        return counts

    def _find_first_action_on_service(
        self,
        history: EpisodeHistory,
        service: str,
        action_types: list[ActionType] = None
    ) -> tuple[int, Any]:
        """
        Find the first action targeting a specific service.

        Returns:
            Tuple of (step_number, action) or (-1, None) if not found
        """
        for i, action in enumerate(history.actions):
            if action.target_service == service:
                if action_types is None or action.action_type in action_types:
                    return (i + 1, action)
        return (-1, None)

    def _check_action_sequence(
        self,
        history: EpisodeHistory,
        expected_sequence: list[tuple[ActionType, str]]
    ) -> tuple[bool, int]:
        """
        Check if actions match expected sequence (in order but not necessarily consecutive).

        Returns:
            Tuple of (all_matched, matches_count)
        """
        seq_idx = 0
        matches = 0

        for action in history.actions:
            if seq_idx >= len(expected_sequence):
                break

            expected_type, expected_service = expected_sequence[seq_idx]
            if action.action_type == expected_type and action.target_service == expected_service:
                matches += 1
                seq_idx += 1

        return (seq_idx >= len(expected_sequence), matches)

    def _was_incident_resolved(self, history: EpisodeHistory) -> bool:
        """Check if the incident was resolved"""
        if history.final_state:
            return history.final_state.get("termination_reason") == "incident_resolved"
        return False

    def _was_catastrophic(self, history: EpisodeHistory) -> bool:
        """Check if a catastrophic action was taken"""
        if history.final_state:
            return history.final_state.get("termination_reason") == "catastrophic_action_taken"
        return False


def grade_episode(task_id: str, history: EpisodeHistory) -> GraderResult:
    """
    Grade an episode using the appropriate task grader.

    Args:
        task_id: The task ID
        history: Episode history

    Returns:
        GraderResult
    """
    from .task1_grader import Task1Grader
    from .task2_grader import Task2Grader
    from .task3_grader import Task3Grader

    graders = {
        "task_1_single_service_crash": Task1Grader(),
        "task_2_db_cascade_failure": Task2Grader(),
        "task_3_distributed_ghost_incident": Task3Grader(),
    }

    if task_id not in graders:
        return GraderResult(
            score=0.0,
            breakdown={"error": "Unknown task_id"},
            feedback=f"Unknown task_id: {task_id}",
        )

    return graders[task_id].grade(history)
