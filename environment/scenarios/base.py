"""Base scenario class for SRE Incident Environment"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
import uuid

from pydantic import BaseModel

from ..models import (
    SREObservation,
    SREAction,
    Alert,
    ServiceMetrics,
    LogLine,
    Deploy,
    ServiceStatus,
    ActionType,
)


class ScenarioConfig(BaseModel):
    """Configuration for a scenario"""
    task_id: str
    name: str
    difficulty: str
    description: str
    target_score: str
    services_affected: list[str]
    root_cause_services: list[str]
    root_cause_description: str
    noise_level: str  # low, medium, high
    red_herrings: list[str]
    optimal_actions: list[dict[str, Any]]
    catastrophic_actions: list[dict[str, str]]  # Actions that make things worse


class BaseScenario(ABC):
    """Base class for all scenarios"""

    def __init__(self):
        self.config: ScenarioConfig = self._create_config()
        self.base_time = datetime.utcnow()
        self.incident_id = ""

        # State tracking
        self._initial_state: dict[str, Any] = {}
        self._current_state: dict[str, Any] = {}
        self._resolved_services: set[str] = set()
        self._root_cause_identified: bool = False
        self._catastrophic_action_taken: bool = False

    @abstractmethod
    def _create_config(self) -> ScenarioConfig:
        """Create the scenario configuration"""
        pass

    @abstractmethod
    def _generate_initial_metrics(self) -> dict[str, ServiceMetrics]:
        """Generate initial service metrics"""
        pass

    @abstractmethod
    def _generate_initial_alerts(self) -> list[Alert]:
        """Generate initial alerts"""
        pass

    @abstractmethod
    def _generate_initial_logs(self) -> list[LogLine]:
        """Generate initial log lines showing the problem"""
        pass

    @abstractmethod
    def _get_service_graph(self) -> dict[str, list[str]]:
        """Get the service dependency graph"""
        pass

    @abstractmethod
    def _generate_deploys(self) -> list[Deploy]:
        """Generate recent deployments"""
        pass

    @abstractmethod
    def apply_action(
        self,
        action: SREAction,
        current_state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Apply an action and return updated state and action effects.

        Returns:
            Tuple of (new_state, effects_dict)
            effects_dict contains:
                - services_fixed: list[str]
                - services_degraded: list[str]
                - root_cause_addressed: bool
                - catastrophic: bool
                - new_logs: list[LogLine]
        """
        pass

    @abstractmethod
    def is_resolved(self, state: dict[str, Any]) -> bool:
        """Check if the incident is fully resolved"""
        pass

    @abstractmethod
    def get_check_logs_result(self, service: str) -> list[LogLine]:
        """Get logs when agent runs check_logs action on a service"""
        pass

    def generate_initial_observation(self) -> SREObservation:
        """Generate the initial observation for this scenario"""
        self.incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        self.base_time = datetime.utcnow()

        metrics = self._generate_initial_metrics()
        self._initial_state = {
            "metrics": {k: v.model_dump() for k, v in metrics.items()},
            "feature_flags": self._get_initial_feature_flags(),
            "config_changes": self._get_initial_config_state(),
            "circuit_breakers": self._get_initial_circuit_breakers(),
            "slow_queries_active": self._get_initial_slow_queries(),
        }
        self._current_state = self._initial_state.copy()
        self._resolved_services = set()
        self._root_cause_identified = False
        self._catastrophic_action_taken = False

        return SREObservation(
            incident_id=self.incident_id,
            alerts=self._generate_initial_alerts(),
            metrics=metrics,
            logs=self._generate_initial_logs(),
            service_graph=self._get_service_graph(),
            recent_deploys=self._generate_deploys(),
            step_count=0,
            elapsed_sim_minutes=0,
            action_history=[],
        )

    def _get_initial_feature_flags(self) -> dict[str, bool]:
        """Override in subclasses that use feature flags"""
        return {}

    def _get_initial_config_state(self) -> dict[str, Any]:
        """Override in subclasses that track config changes"""
        return {}

    def _get_initial_circuit_breakers(self) -> dict[str, str]:
        """Override in subclasses that use circuit breakers"""
        return {}

    def _get_initial_slow_queries(self) -> bool:
        """Override in subclasses that have slow query issues"""
        return False

    def _format_timestamp(self, minutes_ago: int = 0) -> str:
        """Format a timestamp relative to base time"""
        dt = self.base_time - timedelta(minutes=minutes_ago)
        return dt.isoformat() + "Z"

    def create_healthy_metrics(self, service: str) -> ServiceMetrics:
        """Create healthy service metrics"""
        return ServiceMetrics(
            cpu_pct=25.0 + hash(service) % 20,
            memory_pct=40.0 + hash(service) % 25,
            error_rate_pct=0.1,
            p99_latency_ms=50.0 + hash(service) % 100,
            request_rate_rps=1000.0 + hash(service) % 500,
            status=ServiceStatus.HEALTHY,
        )

    def create_degraded_metrics(self, service: str) -> ServiceMetrics:
        """Create degraded service metrics"""
        return ServiceMetrics(
            cpu_pct=70.0 + hash(service) % 20,
            memory_pct=75.0 + hash(service) % 15,
            error_rate_pct=15.0 + hash(service) % 30,
            p99_latency_ms=500.0 + hash(service) % 1000,
            request_rate_rps=300.0 + hash(service) % 200,
            status=ServiceStatus.DEGRADED,
        )

    def create_down_metrics(self, service: str) -> ServiceMetrics:
        """Create down service metrics"""
        return ServiceMetrics(
            cpu_pct=95.0 + hash(service) % 5,
            memory_pct=90.0 + hash(service) % 10,
            error_rate_pct=100.0,
            p99_latency_ms=0.0,  # No successful requests
            request_rate_rps=0.0,
            status=ServiceStatus.DOWN,
        )

    def get_state(self) -> dict[str, Any]:
        """Get current scenario state"""
        return self._current_state.copy()

    def update_state(self, new_state: dict[str, Any]) -> None:
        """Update scenario state"""
        self._current_state = new_state

    @property
    def task_id(self) -> str:
        return self.config.task_id

    @property
    def root_cause_services(self) -> list[str]:
        return self.config.root_cause_services

    @property
    def catastrophic_actions(self) -> list[dict[str, str]]:
        return self.config.catastrophic_actions
