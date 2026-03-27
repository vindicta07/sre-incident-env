"""Reward Calculator for SRE Incident Environment

Implements dense + shaped reward function.
"""

from typing import Any

from .models import SREAction, SREReward, ActionType


class RewardCalculator:
    """
    Calculates rewards for SRE actions.

    Philosophy: Every step gives signal. Agent is rewarded for
    moving toward resolution, penalized for worsening the incident.
    """

    # Reward signals
    INCIDENT_RESOLVED = 1.0
    ROOT_CAUSE_IDENTIFIED = 0.4
    CORRECT_ACTION_TYPE = 0.3
    PARTIAL_RESOLUTION = 0.2
    GOOD_REASONING = 0.1

    # Penalty signals
    WRONG_SERVICE_TARGETED = -0.1
    WRONG_ACTION_TYPE = -0.15
    UNNECESSARY_ESCALATION = -0.1
    CATASTROPHIC_ACTION = -0.5
    TIME_PENALTY_PER_STEP = -0.02  # After step 5
    NOOP_ABUSE = -0.05  # Per consecutive noop

    # Action type mappings for "correct action" detection
    PROBLEM_ACTION_MAPPING = {
        "bad_deploy": [ActionType.ROLLBACK_DEPLOY],
        "slow_queries": [ActionType.KILL_SLOW_QUERIES, ActionType.RUN_SQL_QUERY],
        "feature_flag": [ActionType.TOGGLE_FEATURE_FLAG],
        "config_change": [ActionType.REVERT_CONFIG_CHANGE],
        "circuit_breaker": [ActionType.RESTART_SERVICE],
        "resource_exhaustion": [ActionType.SCALE_UP, ActionType.ADD_CACHE_NODE],
        "cache_issue": [ActionType.FLUSH_CACHE, ActionType.ADD_CACHE_NODE],
    }

    def __init__(self):
        self.previous_affected_count = 0
        self.root_cause_ever_addressed = False

    def reset(self, initial_affected_count: int = 0):
        """Reset calculator for new episode"""
        self.previous_affected_count = initial_affected_count
        self.root_cause_ever_addressed = False

    def calculate(
        self,
        action: SREAction,
        effects: dict[str, Any],
        step_count: int,
        scenario_config: dict[str, Any],
    ) -> SREReward:
        """
        Calculate reward for an action.

        Args:
            action: The action taken
            effects: Effects dict from simulator containing:
                - is_resolved: bool
                - root_cause_addressed: bool
                - catastrophic: bool
                - services_fixed: list[str]
                - services_degraded: list[str]
                - consecutive_noops: int
            step_count: Current step number
            scenario_config: Scenario configuration containing:
                - root_cause_services: list[str]
                - root_cause_type: str (optional)

        Returns:
            SREReward with total, breakdown, and feedback
        """
        breakdown = {}
        feedback_parts = []

        # 1. Check for incident resolution (highest reward)
        if effects.get("is_resolved"):
            breakdown["incident_resolved"] = self.INCIDENT_RESOLVED
            feedback_parts.append("Incident fully resolved!")

        # 2. Check for catastrophic action (severe penalty)
        if effects.get("catastrophic"):
            breakdown["catastrophic_action"] = self.CATASTROPHIC_ACTION
            feedback_parts.append("CRITICAL: Catastrophic action taken!")

        # 3. Check if root cause was addressed
        if effects.get("root_cause_addressed") and not self.root_cause_ever_addressed:
            breakdown["root_cause_identified"] = self.ROOT_CAUSE_IDENTIFIED
            feedback_parts.append("Root cause addressed!")
            self.root_cause_ever_addressed = True

        # 4. Check for partial resolution (services fixed)
        services_fixed = effects.get("services_fixed", [])
        if services_fixed and not effects.get("is_resolved"):
            breakdown["partial_resolution"] = self.PARTIAL_RESOLUTION
            feedback_parts.append(f"Services recovered: {', '.join(services_fixed)}")

        # 5. Check if targeting correct service (root cause)
        root_cause_services = scenario_config.get("root_cause_services", [])
        if action.target_service in root_cause_services:
            # Only reward if not a noop
            if action.action_type != ActionType.NOOP:
                breakdown["correct_target"] = 0.05
                feedback_parts.append(f"Correctly targeted {action.target_service}")
        elif action.action_type != ActionType.NOOP and action.action_type != ActionType.CHECK_LOGS:
            # Check if targeting a healthy service (wasteful)
            if action.target_service not in scenario_config.get("services_affected", []):
                breakdown["wrong_service"] = self.WRONG_SERVICE_TARGETED
                feedback_parts.append(f"Warning: {action.target_service} is not affected")

        # 6. Check for services degraded (made things worse)
        services_degraded = effects.get("services_degraded", [])
        if services_degraded:
            breakdown["services_degraded"] = -0.1 * len(services_degraded)
            feedback_parts.append(f"Services degraded: {', '.join(services_degraded)}")

        # 7. Time penalty after step 5
        if step_count > 5:
            time_penalty = self.TIME_PENALTY_PER_STEP * (step_count - 5)
            breakdown["time_penalty"] = time_penalty
            feedback_parts.append(f"Time pressure: step {step_count}")

        # 8. Noop abuse penalty
        consecutive_noops = effects.get("consecutive_noops", 0)
        if consecutive_noops > 1:
            noop_penalty = self.NOOP_ABUSE * (consecutive_noops - 1)
            breakdown["noop_abuse"] = noop_penalty
            feedback_parts.append(f"Warning: {consecutive_noops} consecutive noops")

        # 9. Unnecessary escalation penalty
        if action.action_type == ActionType.ESCALATE_TO_TEAM:
            # Check if this was a solvable incident
            if scenario_config.get("difficulty") in ["easy", "medium"]:
                breakdown["unnecessary_escalation"] = self.UNNECESSARY_ESCALATION
                feedback_parts.append("Unnecessary escalation for solvable incident")

        # 10. Good reasoning bonus (simple keyword matching)
        if action.reasoning:
            reasoning_keywords = self._extract_reasoning_quality(
                action.reasoning,
                root_cause_services,
                scenario_config.get("root_cause_description", "")
            )
            if reasoning_keywords >= 2:
                breakdown["good_reasoning"] = self.GOOD_REASONING
                feedback_parts.append("Good diagnostic reasoning")

        # 11. Check_logs is always slightly positive (investigation)
        if action.action_type == ActionType.CHECK_LOGS:
            if action.target_service in scenario_config.get("services_affected", []):
                breakdown["investigation"] = 0.02
                feedback_parts.append(f"Investigating {action.target_service} logs")

        # Calculate total
        total = sum(breakdown.values())

        return SREReward(
            total=round(total, 4),
            breakdown=breakdown,
            feedback=" | ".join(feedback_parts) if feedback_parts else "Action taken.",
        )

    def _extract_reasoning_quality(
        self,
        reasoning: str,
        root_cause_services: list[str],
        root_cause_description: str
    ) -> int:
        """
        Score reasoning quality based on keyword matching.

        Returns count of relevant keywords/phrases found.
        """
        reasoning_lower = reasoning.lower()
        score = 0

        # Check for root cause service mentions
        for service in root_cause_services:
            if service.lower() in reasoning_lower:
                score += 1

        # Check for diagnostic terms
        diagnostic_terms = [
            "root cause", "deploy", "rollback", "timeout", "connection",
            "circuit breaker", "cascade", "downstream", "upstream",
            "feature flag", "slow query", "config", "retry"
        ]
        for term in diagnostic_terms:
            if term in reasoning_lower:
                score += 1

        # Check for keywords from root cause description
        if root_cause_description:
            desc_words = root_cause_description.lower().split()
            for word in desc_words:
                if len(word) > 4 and word in reasoning_lower:
                    score += 1

        return min(score, 5)  # Cap at 5
