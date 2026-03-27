"""Task 3 Grader: Distributed Ghost Incident

Scoring:
- 1.0: Perfect: nginx revert + payment restart in correct order ≤6 steps
- 0.8: Both root causes fixed but in wrong order or extra steps
- 0.6: Fixed nginx only — partial recovery
- 0.5: Fixed payment circuit breaker only — partial recovery
- 0.3: Identified both root causes in reasoning but wrong actions
- 0.1: Correctly did not act on red herrings but no fixes
- 0.0: Scaled up (made retry storm worse) or catastrophic action
"""

from environment.models import EpisodeHistory, GraderResult, ActionType
from .grader import Grader


class Task3Grader(Grader):
    """Grader for Task 3: Distributed Ghost Incident"""

    NGINX_SERVICE = "nginx-ingress"
    PAYMENT_SERVICE = "payment-service"
    RED_HERRING_SERVICES = ["notification-service", "user-service"]

    def grade(self, history: EpisodeHistory) -> GraderResult:
        """Grade the episode"""
        breakdown = {
            "reverted_nginx_config": False,
            "restarted_payment": False,
            "nginx_fixed_first": False,
            "scaled_up_bad_service": False,
            "acted_on_red_herrings": False,
            "acknowledged_notification": False,
            "checked_nginx_logs": False,
            "checked_payment_logs": False,
            "steps_to_resolution": history.total_steps,
            "incident_resolved": self._was_incident_resolved(history),
            "catastrophic_action": self._was_catastrophic(history),
        }

        # Track order of key fixes
        nginx_fix_step = -1
        payment_fix_step = -1

        # Analyze actions
        for i, action in enumerate(history.actions):
            step = i + 1

            # Check for nginx revert
            if (action.action_type == ActionType.REVERT_CONFIG_CHANGE and
                action.target_service == self.NGINX_SERVICE):
                breakdown["reverted_nginx_config"] = True
                nginx_fix_step = step

            # Check for payment restart (resets circuit breaker)
            if (action.action_type == ActionType.RESTART_SERVICE and
                action.target_service == self.PAYMENT_SERVICE):
                breakdown["restarted_payment"] = True
                payment_fix_step = step

            # Check for catastrophic scale up
            if action.action_type == ActionType.SCALE_UP:
                if action.target_service in [self.NGINX_SERVICE, self.PAYMENT_SERVICE]:
                    breakdown["scaled_up_bad_service"] = True

            # Check for red herring actions
            if action.target_service in self.RED_HERRING_SERVICES:
                if action.action_type not in [ActionType.CHECK_LOGS, ActionType.ACKNOWLEDGE_ALERT]:
                    breakdown["acted_on_red_herrings"] = True

                if action.action_type == ActionType.ACKNOWLEDGE_ALERT:
                    breakdown["acknowledged_notification"] = True

            # Check for log checks
            if action.action_type == ActionType.CHECK_LOGS:
                if action.target_service == self.NGINX_SERVICE:
                    breakdown["checked_nginx_logs"] = True
                elif action.target_service == self.PAYMENT_SERVICE:
                    breakdown["checked_payment_logs"] = True

        # Determine if nginx was fixed first
        if nginx_fix_step != -1 and payment_fix_step != -1:
            breakdown["nginx_fixed_first"] = nginx_fix_step < payment_fix_step

        # Calculate score

        # Catastrophic: scaled up during retry storm
        if breakdown["scaled_up_bad_service"] or breakdown["catastrophic_action"]:
            return GraderResult(
                score=0.0,
                breakdown=breakdown,
                feedback="Scaled up during retry storm - made the problem worse! Score: 0.0",
            )

        # Perfect: Both fixes in correct order within 6 steps
        if breakdown["reverted_nginx_config"] and breakdown["restarted_payment"]:
            if breakdown["nginx_fixed_first"] and history.total_steps <= 6:
                return GraderResult(
                    score=1.0,
                    breakdown=breakdown,
                    feedback="Perfect! Fixed nginx config then reset circuit breaker in ≤6 steps. Score: 1.0",
                )
            # Both fixed but wrong order or many steps
            return GraderResult(
                score=0.8,
                breakdown=breakdown,
                feedback="Both root causes fixed, but order or efficiency could be improved. Score: 0.8",
            )

        # Partial: Fixed nginx only
        if breakdown["reverted_nginx_config"] and not breakdown["restarted_payment"]:
            return GraderResult(
                score=0.6,
                breakdown=breakdown,
                feedback="Fixed nginx timeout but circuit breaker still tripped. Partial recovery. Score: 0.6",
            )

        # Partial: Fixed payment only
        if breakdown["restarted_payment"] and not breakdown["reverted_nginx_config"]:
            return GraderResult(
                score=0.5,
                breakdown=breakdown,
                feedback="Reset circuit breaker but nginx timeout still causing issues. Partial. Score: 0.5",
            )

        # Checked correct logs but no fixes
        if breakdown["checked_nginx_logs"] and breakdown["checked_payment_logs"]:
            return GraderResult(
                score=0.3,
                breakdown=breakdown,
                feedback="Investigated correct services but didn't take remediation actions. Score: 0.3",
            )

        # Avoided red herrings but no progress
        if not breakdown["acted_on_red_herrings"] and breakdown["acknowledged_notification"]:
            return GraderResult(
                score=0.1,
                breakdown=breakdown,
                feedback="Correctly ignored red herrings but didn't fix root causes. Score: 0.1",
            )

        # No meaningful progress
        if breakdown["acted_on_red_herrings"]:
            return GraderResult(
                score=0.05,
                breakdown=breakdown,
                feedback="Acted on red herring services instead of root causes. Score: 0.05",
            )

        return GraderResult(
            score=0.0,
            breakdown=breakdown,
            feedback="No progress toward resolution. Score: 0.0",
        )
