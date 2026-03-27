"""Task 1: Single Service Crash Scenario (Easy)

Root Cause: Bad deploy v2.3.1 on auth-service introduced a null pointer exception
Solution: Rollback auth-service to v2.3.0
"""

from typing import Any

from ..models import (
    Alert,
    ServiceMetrics,
    LogLine,
    Deploy,
    SREAction,
    ActionType,
    Severity,
    LogLevel,
    ServiceStatus,
)
from .base import BaseScenario, ScenarioConfig


class SingleServiceCrashScenario(BaseScenario):
    """Easy scenario: Single service crash due to bad deploy"""

    def _create_config(self) -> ScenarioConfig:
        return ScenarioConfig(
            task_id="task_1_single_service_crash",
            name="Single Service Crash",
            difficulty="easy",
            description=(
                "One microservice (auth-service) is down due to a bad deploy 30 minutes ago. "
                "CPU is spiking, error rate is 100%, all other services are healthy. "
                "Agent must identify the bad deploy and rollback."
            ),
            target_score="0.8-1.0",
            services_affected=["auth-service"],
            root_cause_services=["auth-service"],
            root_cause_description="Bad deploy v2.3.1 introduced a null pointer exception on startup",
            noise_level="low",
            red_herrings=["api-gateway shows elevated latency (downstream effect, not root cause)"],
            optimal_actions=[
                {"action_type": "check_logs", "target_service": "auth-service"},
                {"action_type": "rollback_deploy", "target_service": "auth-service", "parameters": {"version": "v2.3.0"}},
            ],
            catastrophic_actions=[
                {"action_type": "scale_down", "target_service": "auth-service"},
            ],
        )

    def _get_service_graph(self) -> dict[str, list[str]]:
        return {
            "api-gateway": ["auth-service", "user-service", "order-service"],
            "user-service": ["postgres-primary", "redis-cache"],
            "order-service": ["postgres-primary", "payment-service"],
            "auth-service": ["redis-cache"],
            "payment-service": ["postgres-primary"],
            "postgres-primary": [],
            "redis-cache": [],
        }

    def _generate_initial_metrics(self) -> dict[str, ServiceMetrics]:
        services = list(self._get_service_graph().keys())
        metrics = {}

        for service in services:
            if service == "auth-service":
                # Down: CPU spike, 100% error rate
                metrics[service] = ServiceMetrics(
                    cpu_pct=98.5,
                    memory_pct=85.0,
                    error_rate_pct=100.0,
                    p99_latency_ms=0.0,
                    request_rate_rps=0.0,
                    status=ServiceStatus.DOWN,
                )
            elif service == "api-gateway":
                # Degraded due to auth-service being down (red herring)
                metrics[service] = ServiceMetrics(
                    cpu_pct=45.0,
                    memory_pct=55.0,
                    error_rate_pct=35.0,
                    p99_latency_ms=1200.0,
                    request_rate_rps=850.0,
                    status=ServiceStatus.DEGRADED,
                )
            else:
                metrics[service] = self.create_healthy_metrics(service)

        return metrics

    def _generate_initial_alerts(self) -> list[Alert]:
        return [
            Alert(
                service="auth-service",
                severity=Severity.P1,
                message="Service auth-service is DOWN - 100% error rate, no successful requests",
                fired_at=self._format_timestamp(minutes_ago=25),
                acknowledged=False,
            ),
            Alert(
                service="api-gateway",
                severity=Severity.P2,
                message="Elevated latency on api-gateway - p99 > 1000ms",
                fired_at=self._format_timestamp(minutes_ago=24),
                acknowledged=False,
            ),
            Alert(
                service="auth-service",
                severity=Severity.P1,
                message="auth-service CPU utilization > 95%",
                fired_at=self._format_timestamp(minutes_ago=26),
                acknowledged=False,
            ),
        ]

    def _generate_initial_logs(self) -> list[LogLine]:
        logs = [
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=30),
                service="auth-service",
                level=LogLevel.INFO,
                message="Deploying version v2.3.1...",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=29),
                service="auth-service",
                level=LogLevel.INFO,
                message="Deployment v2.3.1 completed, restarting service...",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=28),
                service="auth-service",
                level=LogLevel.ERROR,
                message="FATAL: NullPointerException in AuthController.validateToken() at line 142",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=28),
                service="auth-service",
                level=LogLevel.FATAL,
                message="Application failed to start - shutting down",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=27),
                service="auth-service",
                level=LogLevel.ERROR,
                message="Restart attempt 1/3 failed: NullPointerException in AuthController.validateToken()",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=26),
                service="auth-service",
                level=LogLevel.ERROR,
                message="Restart attempt 2/3 failed: NullPointerException in AuthController.validateToken()",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=25),
                service="auth-service",
                level=LogLevel.FATAL,
                message="Max restart attempts reached. Service marked as DOWN.",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=24),
                service="api-gateway",
                level=LogLevel.WARN,
                message="Upstream auth-service not responding, requests timing out",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=23),
                service="api-gateway",
                level=LogLevel.ERROR,
                message="Circuit breaker OPEN for auth-service after 10 consecutive failures",
            ),
        ]
        return logs

    def _generate_deploys(self) -> list[Deploy]:
        return [
            Deploy(
                service="auth-service",
                version="v2.3.1",
                deployed_at=self._format_timestamp(minutes_ago=30),
                deployed_by="deploy-bot",
                is_rollback_target=False,
            ),
            Deploy(
                service="auth-service",
                version="v2.3.0",
                deployed_at=self._format_timestamp(minutes_ago=180),  # 3 hours ago
                deployed_by="alice@company.com",
                is_rollback_target=True,
            ),
            Deploy(
                service="user-service",
                version="v4.1.2",
                deployed_at=self._format_timestamp(minutes_ago=120),  # 2 hours ago
                deployed_by="bob@company.com",
                is_rollback_target=True,
            ),
        ]

    def get_check_logs_result(self, service: str) -> list[LogLine]:
        """Get detailed logs when agent checks logs on a service"""
        if service == "auth-service":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=30),
                    service="auth-service",
                    level=LogLevel.INFO,
                    message="Starting deployment of v2.3.1",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=29),
                    service="auth-service",
                    level=LogLevel.INFO,
                    message="Loading new AuthController module...",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=28),
                    service="auth-service",
                    level=LogLevel.ERROR,
                    message="java.lang.NullPointerException: Cannot invoke method on null object",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=28),
                    service="auth-service",
                    level=LogLevel.ERROR,
                    message="    at com.company.auth.AuthController.validateToken(AuthController.java:142)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=28),
                    service="auth-service",
                    level=LogLevel.ERROR,
                    message="    at com.company.auth.AuthController.init(AuthController.java:45)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=28),
                    service="auth-service",
                    level=LogLevel.FATAL,
                    message="CRITICAL: Service startup failed. This appears to be a regression in v2.3.1",
                ),
            ]
        elif service == "api-gateway":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=24),
                    service="api-gateway",
                    level=LogLevel.WARN,
                    message="Upstream service auth-service connection refused",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=23),
                    service="api-gateway",
                    level=LogLevel.ERROR,
                    message="Too many failures to auth-service, opening circuit breaker",
                ),
            ]
        else:
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=5),
                    service=service,
                    level=LogLevel.INFO,
                    message=f"{service} operating normally",
                ),
            ]

    def apply_action(
        self,
        action: SREAction,
        current_state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Apply action and return updated state and effects"""
        new_state = current_state.copy()
        effects = {
            "services_fixed": [],
            "services_degraded": [],
            "root_cause_addressed": False,
            "catastrophic": False,
            "new_logs": [],
        }

        if action.action_type == ActionType.ROLLBACK_DEPLOY:
            if action.target_service == "auth-service":
                # This fixes the root cause!
                new_state["metrics"]["auth-service"] = self.create_healthy_metrics("auth-service").model_dump()
                new_state["metrics"]["api-gateway"] = self.create_healthy_metrics("api-gateway").model_dump()
                effects["services_fixed"] = ["auth-service", "api-gateway"]
                effects["root_cause_addressed"] = True
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="auth-service",
                    level=LogLevel.INFO,
                    message="Rollback to v2.3.0 successful. Service starting...",
                ))
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="auth-service",
                    level=LogLevel.INFO,
                    message="auth-service v2.3.0 started successfully. All health checks passing.",
                ))

        elif action.action_type == ActionType.RESTART_SERVICE:
            if action.target_service == "auth-service":
                # Restart won't fix the issue - it's a code bug
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="auth-service",
                    level=LogLevel.ERROR,
                    message="Restart attempted but service still failing with NullPointerException",
                ))

        elif action.action_type == ActionType.SCALE_DOWN:
            if action.target_service == "auth-service":
                # This is catastrophic - scaling down an already dead service
                effects["catastrophic"] = True
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="auth-service",
                    level=LogLevel.WARN,
                    message="Scale down command received for already-down service",
                ))

        elif action.action_type == ActionType.CHECK_LOGS:
            # Just informational, no state change
            pass

        elif action.action_type == ActionType.ACKNOWLEDGE_ALERT:
            # Mark alerts as acknowledged
            pass

        return new_state, effects

    def is_resolved(self, state: dict[str, Any]) -> bool:
        """Check if incident is fully resolved"""
        auth_metrics = state.get("metrics", {}).get("auth-service", {})
        api_metrics = state.get("metrics", {}).get("api-gateway", {})

        auth_healthy = auth_metrics.get("status") == ServiceStatus.HEALTHY.value
        api_healthy = api_metrics.get("status") == ServiceStatus.HEALTHY.value

        return auth_healthy and api_healthy
