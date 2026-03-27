"""Task 1 Grader: Single Service Crash

Scoring:
- 1.0: Rollback auth-service in ≤3 steps
- 0.7: Rollback auth-service in 4-6 steps
- 0.4: Restart service instead of rollback (works but bad practice)
- 0.1: Identified correct service but took wrong action
- 0.0: Never targeted auth-service
"""

from environment.models import EpisodeHistory, GraderResult, ActionType
from .grader import Grader


class Task1Grader(Grader):
    """Grader for Task 1: Single Service Crash"""

    TARGET_SERVICE = "auth-service"
    OPTIMAL_ACTION = ActionType.ROLLBACK_DEPLOY
    SUBOPTIMAL_ACTION = ActionType.RESTART_SERVICE

    def grade(self, history: EpisodeHistory) -> GraderResult:
        """Grade the episode"""
        breakdown = {
            "targeted_correct_service": False,
            "used_rollback": False,
            "used_restart": False,
            "steps_to_resolution": history.total_steps,
            "incident_resolved": self._was_incident_resolved(history),
            "catastrophic_action": self._was_catastrophic(history),
        }

        # Check if catastrophic action was taken
        if breakdown["catastrophic_action"]:
            return GraderResult(
                score=0.0,
                breakdown=breakdown,
                feedback="Catastrophic action taken. Score: 0.0",
            )

        # Find first action on auth-service
        step, action = self._find_first_action_on_service(history, self.TARGET_SERVICE)

        if step == -1:
            # Never targeted auth-service
            return GraderResult(
                score=0.0,
                breakdown=breakdown,
                feedback="Never targeted auth-service. Score: 0.0",
            )

        breakdown["targeted_correct_service"] = True

        # Check for rollback action
        rollback_step, rollback_action = self._find_first_action_on_service(
            history, self.TARGET_SERVICE, [self.OPTIMAL_ACTION]
        )

        if rollback_step != -1:
            breakdown["used_rollback"] = True

            # Score based on steps to rollback
            if rollback_step <= 3:
                score = 1.0
                feedback = f"Perfect! Rolled back auth-service in {rollback_step} steps. Score: 1.0"
            elif rollback_step <= 6:
                score = 0.7
                feedback = f"Good. Rolled back auth-service in {rollback_step} steps. Score: 0.7"
            else:
                score = 0.5
                feedback = f"Rolled back auth-service but took {rollback_step} steps. Score: 0.5"

            return GraderResult(score=score, breakdown=breakdown, feedback=feedback)

        # Check for restart action (suboptimal)
        restart_step, restart_action = self._find_first_action_on_service(
            history, self.TARGET_SERVICE, [self.SUBOPTIMAL_ACTION]
        )

        if restart_step != -1:
            breakdown["used_restart"] = True

            # Restart doesn't actually fix the issue in our scenario
            # But we give partial credit for identifying the right service
            if breakdown["incident_resolved"]:
                score = 0.4
                feedback = "Used restart instead of rollback. It worked but rollback was the correct action. Score: 0.4"
            else:
                score = 0.3
                feedback = "Tried restart on auth-service but the bug persists. Rollback was needed. Score: 0.3"

            return GraderResult(score=score, breakdown=breakdown, feedback=feedback)

        # Targeted correct service but wrong action
        return GraderResult(
            score=0.1,
            breakdown=breakdown,
            feedback="Identified auth-service but didn't rollback or restart. Score: 0.1",
        )
