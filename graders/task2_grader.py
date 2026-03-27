"""Task 2 Grader: Database Cascade Failure

Scoring:
- 1.0: Correct 4-step resolution: logs → slow queries → kill → flag off
- 0.8: Killed queries + disabled flag (skipped log check)
- 0.6: Disabled flag only (partial fix, slow queries drain naturally)
- 0.4: Restarted downstream services (symptom treatment, not cure)
- 0.2: Identified DB as root cause but no correct action
- 0.0: Escalated without attempting resolution OR catastrophic action
"""

from environment.models import EpisodeHistory, GraderResult, ActionType
from .grader import Grader


class Task2Grader(Grader):
    """Grader for Task 2: Database Cascade Failure"""

    ROOT_CAUSE_SERVICE = "postgres-primary"
    DOWNSTREAM_SERVICES = ["user-service", "order-service"]

    def grade(self, history: EpisodeHistory) -> GraderResult:
        """Grade the episode"""
        breakdown = {
            "checked_db_logs": False,
            "ran_sql_query": False,
            "killed_slow_queries": False,
            "disabled_feature_flag": False,
            "restarted_downstream": False,
            "targeted_db": False,
            "escalated": False,
            "steps_to_resolution": history.total_steps,
            "incident_resolved": self._was_incident_resolved(history),
            "catastrophic_action": self._was_catastrophic(history),
        }

        # Check for catastrophic action
        if breakdown["catastrophic_action"]:
            return GraderResult(
                score=0.0,
                breakdown=breakdown,
                feedback="Catastrophic action taken (e.g., restarted DB during load). Score: 0.0",
            )

        # Analyze actions taken
        for action in history.actions:
            if action.target_service == self.ROOT_CAUSE_SERVICE:
                breakdown["targeted_db"] = True

                if action.action_type == ActionType.CHECK_LOGS:
                    breakdown["checked_db_logs"] = True
                elif action.action_type == ActionType.RUN_SQL_QUERY:
                    breakdown["ran_sql_query"] = True
                elif action.action_type == ActionType.KILL_SLOW_QUERIES:
                    breakdown["killed_slow_queries"] = True
                elif action.action_type == ActionType.TOGGLE_FEATURE_FLAG:
                    breakdown["disabled_feature_flag"] = True

            elif action.target_service in self.DOWNSTREAM_SERVICES:
                if action.action_type == ActionType.RESTART_SERVICE:
                    breakdown["restarted_downstream"] = True

            if action.action_type == ActionType.ESCALATE_TO_TEAM:
                breakdown["escalated"] = True

        # Check for toggle_feature_flag with any target (it's a global action)
        for action in history.actions:
            if action.action_type == ActionType.TOGGLE_FEATURE_FLAG:
                params = action.parameters or {}
                if params.get("flag") == "new_dashboard" and params.get("state") is False:
                    breakdown["disabled_feature_flag"] = True

        # Calculate score
        if breakdown["escalated"] and not breakdown["targeted_db"]:
            return GraderResult(
                score=0.0,
                breakdown=breakdown,
                feedback="Escalated without attempting resolution. Score: 0.0",
            )

        # Perfect score: All 4 key actions
        if (breakdown["checked_db_logs"] and
            (breakdown["ran_sql_query"] or breakdown["killed_slow_queries"]) and
            breakdown["killed_slow_queries"] and
            breakdown["disabled_feature_flag"]):

            return GraderResult(
                score=1.0,
                breakdown=breakdown,
                feedback="Perfect! Investigated logs, killed slow queries, and disabled feature flag. Score: 1.0",
            )

        # Good score: Killed queries + disabled flag (skipped investigation)
        if breakdown["killed_slow_queries"] and breakdown["disabled_feature_flag"]:
            return GraderResult(
                score=0.8,
                breakdown=breakdown,
                feedback="Good. Killed queries and disabled flag, but skipped log investigation. Score: 0.8",
            )

        # Partial: Disabled flag only
        if breakdown["disabled_feature_flag"] and not breakdown["killed_slow_queries"]:
            return GraderResult(
                score=0.6,
                breakdown=breakdown,
                feedback="Disabled feature flag but didn't kill existing slow queries. Partial fix. Score: 0.6",
            )

        # Partial: Killed queries only
        if breakdown["killed_slow_queries"] and not breakdown["disabled_feature_flag"]:
            return GraderResult(
                score=0.5,
                breakdown=breakdown,
                feedback="Killed slow queries but didn't disable feature flag. Issue will recur. Score: 0.5",
            )

        # Symptom treatment: Restarted downstream services
        if breakdown["restarted_downstream"] and not breakdown["targeted_db"]:
            return GraderResult(
                score=0.4,
                breakdown=breakdown,
                feedback="Treated symptoms (restarted downstream) instead of addressing root cause. Score: 0.4",
            )

        # Identified DB but wrong actions
        if breakdown["targeted_db"]:
            return GraderResult(
                score=0.2,
                breakdown=breakdown,
                feedback="Identified postgres-primary as root cause but didn't take correct remediation. Score: 0.2",
            )

        # Never identified root cause
        return GraderResult(
            score=0.1,
            breakdown=breakdown,
            feedback="Did not identify or address the database root cause. Score: 0.1",
        )
