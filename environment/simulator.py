"""Service State Simulator for SRE Incident Environment

Handles applying actions and updating service state.
"""

from typing import Any

from .models import (
    SREObservation,
    SREAction,
    ActionType,
    ServiceMetrics,
    LogLine,
    Alert,
    ServiceStatus,
)
from .scenarios.base import BaseScenario


class ServiceSimulator:
    """Simulates service state changes based on actions"""

    def __init__(self, scenario: BaseScenario):
        self.scenario = scenario
        self.state: dict[str, Any] = {}
        self.step_count = 0
        self.elapsed_minutes = 0
        self.action_history: list[str] = []
        self.consecutive_noops = 0

    def reset(self) -> SREObservation:
        """Reset simulator with new scenario observation"""
        observation = self.scenario.generate_initial_observation()
        self.state = self.scenario.get_state()
        self.step_count = 0
        self.elapsed_minutes = 0
        self.action_history = []
        self.consecutive_noops = 0
        return observation

    def apply_action(self, action: SREAction, current_obs: SREObservation) -> tuple[SREObservation, dict[str, Any]]:
        """
        Apply an action and return updated observation and effects.

        Returns:
            Tuple of (new_observation, effects_dict)
        """
        self.step_count += 1
        self.elapsed_minutes += 2  # Each step = 2 simulated minutes

        # Track noops
        if action.action_type == ActionType.NOOP:
            self.consecutive_noops += 1
        else:
            self.consecutive_noops = 0

        # Apply action via scenario
        new_state, effects = self.scenario.apply_action(action, self.state)
        self.state = new_state
        self.scenario.update_state(new_state)

        # Handle check_logs specially - adds logs to observation
        new_logs = list(current_obs.logs)
        if action.action_type == ActionType.CHECK_LOGS:
            check_logs_result = self.scenario.get_check_logs_result(action.target_service)
            new_logs.extend(check_logs_result)
            effects["check_logs_result"] = check_logs_result

        # Add any new logs from the action effects
        if effects.get("new_logs"):
            new_logs.extend(effects["new_logs"])

        # Keep only last 50 logs
        new_logs = new_logs[-50:]

        # Build new metrics from state
        new_metrics = {}
        for service, metrics_dict in self.state.get("metrics", {}).items():
            new_metrics[service] = ServiceMetrics(**metrics_dict)

        # Update alerts - mark as acknowledged if that action was taken
        new_alerts = list(current_obs.alerts)
        if action.action_type == ActionType.ACKNOWLEDGE_ALERT:
            for alert in new_alerts:
                if alert.service == action.target_service:
                    alert.acknowledged = True

        # Add action to history
        action_summary = f"Step {self.step_count}: {action.action_type.value} on {action.target_service}"
        if action.reasoning:
            action_summary += f" ({action.reasoning[:50]}...)" if len(action.reasoning) > 50 else f" ({action.reasoning})"
        self.action_history.append(action_summary)

        # Create new observation
        new_obs = SREObservation(
            incident_id=current_obs.incident_id,
            alerts=new_alerts,
            metrics=new_metrics,
            logs=new_logs,
            service_graph=current_obs.service_graph,
            recent_deploys=current_obs.recent_deploys,
            step_count=self.step_count,
            elapsed_sim_minutes=self.elapsed_minutes,
            action_history=self.action_history.copy(),
        )

        # Add additional effects info
        effects["is_resolved"] = self.scenario.is_resolved(self.state)
        effects["consecutive_noops"] = self.consecutive_noops

        return new_obs, effects

    def is_catastrophic(self, action: SREAction) -> bool:
        """Check if an action is catastrophic for this scenario"""
        for catastrophic in self.scenario.catastrophic_actions:
            if (action.action_type.value == catastrophic.get("action_type") and
                action.target_service == catastrophic.get("target_service")):
                return True
        return False

    def is_correct_target(self, action: SREAction) -> bool:
        """Check if action targets a root cause service"""
        return action.target_service in self.scenario.root_cause_services

    def is_healthy_service(self, service: str) -> bool:
        """Check if a service is healthy"""
        metrics = self.state.get("metrics", {}).get(service, {})
        return metrics.get("status") == ServiceStatus.HEALTHY.value

    def get_affected_services_count(self) -> int:
        """Count number of affected (non-healthy) services"""
        count = 0
        for service, metrics_dict in self.state.get("metrics", {}).items():
            if metrics_dict.get("status") != ServiceStatus.HEALTHY.value:
                count += 1
        return count

    def get_resolved_services_count(self) -> int:
        """Count number of services that were affected but are now healthy"""
        total_healthy = 0
        for service, metrics_dict in self.state.get("metrics", {}).items():
            if metrics_dict.get("status") == ServiceStatus.HEALTHY.value:
                total_healthy += 1
        return total_healthy
