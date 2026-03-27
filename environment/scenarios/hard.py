"""Task 3: Distributed Ghost Incident Scenario (Hard)

Root Cause: nginx timeout set to 100ms (was 5s) causing retry storms + circuit breaker cascade
Solution: Revert nginx config + restart payment-service to reset circuit breakers
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


class DistributedGhostScenario(BaseScenario):
    """Hard scenario: Distributed ghost incident with retry storms"""

    def _create_config(self) -> ScenarioConfig:
        return ScenarioConfig(
            task_id="task_3_distributed_ghost_incident",
            name="Distributed Ghost Incident",
            difficulty="hard",
            description=(
                "Multiple services are throwing intermittent 5xx errors in a subtle pattern. "
                "Root cause is a misconfigured nginx timeout (100ms instead of 5s) causing retry storms, "
                "which are amplified by circuit breakers. Agent must correlate timing patterns, "
                "fix nginx config, and reset circuit breakers. Wrong actions make retry storm worse."
            ),
            target_score="0.3-0.7",
            services_affected=["payment-service", "nginx-ingress", "notification-service", "api-gateway"],
            root_cause_services=["nginx-ingress", "payment-service"],
            root_cause_description="nginx timeout config set to 100ms (was 5s) causing retry storms → circuit breaker opens → cascading 503s",
            noise_level="high",
            red_herrings=[
                "notification-service errors (actually unrelated queue backlog)",
                "Recent memory spike on api-gateway (GC pause, not the issue)",
                "P2 alert on user-service (it was already degraded before incident)",
            ],
            optimal_actions=[
                {"action_type": "check_logs", "target_service": "nginx-ingress"},
                {"action_type": "revert_config_change", "target_service": "nginx-ingress"},
                {"action_type": "check_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
                {"action_type": "acknowledge_alert", "target_service": "notification-service"},
            ],
            catastrophic_actions=[
                {"action_type": "scale_up", "target_service": "payment-service"},  # Makes retry storm worse
                {"action_type": "scale_up", "target_service": "nginx-ingress"},  # Amplifies the problem
            ],
        )

    def _get_service_graph(self) -> dict[str, list[str]]:
        return {
            "nginx-ingress": ["api-gateway"],
            "api-gateway": ["auth-service", "user-service", "order-service", "payment-service"],
            "user-service": ["postgres-primary", "redis-cache"],
            "order-service": ["postgres-primary", "payment-service"],
            "auth-service": ["redis-cache"],
            "payment-service": ["payment-gateway-ext", "postgres-primary"],
            "notification-service": ["redis-cache", "email-service-ext"],
            "postgres-primary": [],
            "redis-cache": [],
        }

    def _get_initial_config_state(self) -> dict[str, Any]:
        return {
            "nginx-ingress": {
                "timeout_ms": 100,  # Misconfigured! Should be 5000
                "previous_timeout_ms": 5000,
                "changed_at": self._format_timestamp(minutes_ago=45),
                "changed_by": "config-bot",
            }
        }

    def _get_initial_circuit_breakers(self) -> dict[str, str]:
        return {
            "payment-service": "OPEN",  # Tripped due to timeouts
            "api-gateway": "HALF_OPEN",
        }

    def _generate_initial_metrics(self) -> dict[str, ServiceMetrics]:
        services = list(self._get_service_graph().keys())
        metrics = {}

        for service in services:
            if service == "nginx-ingress":
                # High error rate due to timeout
                metrics[service] = ServiceMetrics(
                    cpu_pct=75.0,
                    memory_pct=60.0,
                    error_rate_pct=35.0,
                    p99_latency_ms=110.0,  # Just over the 100ms timeout
                    request_rate_rps=5000.0,  # High due to retries
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "payment-service":
                # Circuit breaker open, intermittent 503s
                metrics[service] = ServiceMetrics(
                    cpu_pct=40.0,
                    memory_pct=55.0,
                    error_rate_pct=60.0,
                    p99_latency_ms=200.0,  # Actually fine, but upstream timing out
                    request_rate_rps=100.0,  # Low due to circuit breaker
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "api-gateway":
                # Degraded, circuit breaker half-open
                metrics[service] = ServiceMetrics(
                    cpu_pct=85.0,  # High due to retry handling
                    memory_pct=70.0,
                    error_rate_pct=25.0,
                    p99_latency_ms=800.0,
                    request_rate_rps=3000.0,
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "notification-service":
                # Red herring - unrelated queue backlog
                metrics[service] = ServiceMetrics(
                    cpu_pct=30.0,
                    memory_pct=85.0,  # High memory due to queue
                    error_rate_pct=15.0,
                    p99_latency_ms=2000.0,
                    request_rate_rps=50.0,
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "user-service":
                # Red herring - pre-existing degradation
                metrics[service] = ServiceMetrics(
                    cpu_pct=55.0,
                    memory_pct=65.0,
                    error_rate_pct=8.0,
                    p99_latency_ms=300.0,
                    request_rate_rps=800.0,
                    status=ServiceStatus.DEGRADED,
                )
            else:
                metrics[service] = self.create_healthy_metrics(service)

        return metrics

    def _generate_initial_alerts(self) -> list[Alert]:
        return [
            Alert(
                service="payment-service",
                severity=Severity.P1,
                message="payment-service circuit breaker OPEN - 60% error rate",
                fired_at=self._format_timestamp(minutes_ago=30),
                acknowledged=False,
            ),
            Alert(
                service="nginx-ingress",
                severity=Severity.P2,
                message="Elevated 504 Gateway Timeout errors on nginx-ingress",
                fired_at=self._format_timestamp(minutes_ago=40),
                acknowledged=False,
            ),
            Alert(
                service="api-gateway",
                severity=Severity.P2,
                message="api-gateway memory pressure - possible GC pause",
                fired_at=self._format_timestamp(minutes_ago=25),
                acknowledged=False,
            ),
            Alert(
                service="notification-service",
                severity=Severity.P3,
                message="notification-service queue backlog > 10000 messages",
                fired_at=self._format_timestamp(minutes_ago=60),  # Pre-existing
                acknowledged=False,
            ),
            Alert(
                service="user-service",
                severity=Severity.P2,
                message="user-service elevated latency",
                fired_at=self._format_timestamp(minutes_ago=120),  # Pre-existing red herring
                acknowledged=False,
            ),
        ]

    def _generate_initial_logs(self) -> list[LogLine]:
        return [
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=45),
                service="nginx-ingress",
                level=LogLevel.INFO,
                message="Config reload: proxy_read_timeout changed from 5000ms to 100ms",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=42),
                service="nginx-ingress",
                level=LogLevel.WARN,
                message="Upstream timeout: payment-service took 150ms (limit: 100ms)",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=40),
                service="api-gateway",
                level=LogLevel.WARN,
                message="Retry storm detected: 500 retries/sec to payment-service",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=35),
                service="payment-service",
                level=LogLevel.ERROR,
                message="Circuit breaker tripped: too many failures in 60s window",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=30),
                service="payment-service",
                level=LogLevel.WARN,
                message="Circuit breaker state: OPEN - rejecting all requests",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=25),
                service="api-gateway",
                level=LogLevel.WARN,
                message="GC pause: 500ms (this is normal under load)",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=20),
                service="notification-service",
                level=LogLevel.WARN,
                message="Queue backlog growing: 12000 pending messages (unrelated to current incident)",
            ),
        ]

    def _generate_deploys(self) -> list[Deploy]:
        return [
            Deploy(
                service="api-gateway",
                version="v5.2.0",
                deployed_at=self._format_timestamp(minutes_ago=180),  # 3 hours ago - not related
                deployed_by="deploy-bot",
                is_rollback_target=True,
            ),
            Deploy(
                service="user-service",
                version="v3.1.0",
                deployed_at=self._format_timestamp(minutes_ago=360),  # 6 hours ago
                deployed_by="alice@company.com",
                is_rollback_target=True,
            ),
        ]

    def get_check_logs_result(self, service: str) -> list[LogLine]:
        """Get detailed logs when agent checks logs on a service"""
        if service == "nginx-ingress":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=45),
                    service="nginx-ingress",
                    level=LogLevel.INFO,
                    message="Configuration change detected: proxy_read_timeout = 100ms (was: 5000ms)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=44),
                    service="nginx-ingress",
                    level=LogLevel.INFO,
                    message="Config applied by: config-bot via automated config sync",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=43),
                    service="nginx-ingress",
                    level=LogLevel.WARN,
                    message="WARNING: New timeout (100ms) is lower than avg payment-service response time (180ms)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=42),
                    service="nginx-ingress",
                    level=LogLevel.ERROR,
                    message="504 Gateway Timeout: upstream payment-service timed out after 100ms",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=41),
                    service="nginx-ingress",
                    level=LogLevel.ERROR,
                    message="High 504 rate detected: 35% of requests to payment-service timing out",
                ),
            ]
        elif service == "payment-service":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=40),
                    service="payment-service",
                    level=LogLevel.INFO,
                    message="Request processing normally (avg response time: 180ms)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=38),
                    service="payment-service",
                    level=LogLevel.WARN,
                    message="High request volume detected - possible retry storm from upstream",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=35),
                    service="payment-service",
                    level=LogLevel.ERROR,
                    message="Circuit breaker OPEN: Failure rate 65% exceeds threshold 50%",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=30),
                    service="payment-service",
                    level=LogLevel.WARN,
                    message="Circuit breaker preventing new requests. State: OPEN. Reset timeout: 60s",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=25),
                    service="payment-service",
                    level=LogLevel.INFO,
                    message="Circuit breaker attempted HALF_OPEN, failed, back to OPEN",
                ),
            ]
        elif service == "api-gateway":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=40),
                    service="api-gateway",
                    level=LogLevel.WARN,
                    message="Retry storm: 500 retries/sec detected on payment-service route",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=38),
                    service="api-gateway",
                    level=LogLevel.WARN,
                    message="Memory pressure increasing due to pending retry requests",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=25),
                    service="api-gateway",
                    level=LogLevel.INFO,
                    message="GC pause: 500ms - normal under high load conditions",
                ),
            ]
        elif service == "notification-service":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=60),
                    service="notification-service",
                    level=LogLevel.WARN,
                    message="Queue backlog: External email provider rate limited us (unrelated to current incident)",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=55),
                    service="notification-service",
                    level=LogLevel.INFO,
                    message="Processing at reduced rate due to external rate limit",
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
        if "config_changes" not in new_state:
            new_state["config_changes"] = self._get_initial_config_state()
        if "circuit_breakers" not in new_state:
            new_state["circuit_breakers"] = self._get_initial_circuit_breakers()

        effects = {
            "services_fixed": [],
            "services_degraded": [],
            "root_cause_addressed": False,
            "catastrophic": False,
            "new_logs": [],
        }

        nginx_fixed = new_state.get("config_changes", {}).get("nginx-ingress", {}).get("timeout_ms", 100) == 5000
        circuit_breaker_reset = new_state.get("circuit_breakers", {}).get("payment-service") == "CLOSED"

        if action.action_type == ActionType.REVERT_CONFIG_CHANGE:
            if action.target_service == "nginx-ingress":
                new_state["config_changes"]["nginx-ingress"]["timeout_ms"] = 5000
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="nginx-ingress",
                    level=LogLevel.INFO,
                    message="Config reverted: proxy_read_timeout restored to 5000ms",
                ))
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="nginx-ingress",
                    level=LogLevel.INFO,
                    message="504 timeout errors should decrease as requests complete normally",
                ))

                # Fix nginx metrics
                new_state["metrics"]["nginx-ingress"] = self.create_healthy_metrics("nginx-ingress").model_dump()
                effects["services_fixed"].append("nginx-ingress")

                # If circuit breaker already reset, fix everything
                if circuit_breaker_reset:
                    self._fix_all_services(new_state, effects)

        elif action.action_type == ActionType.RESTART_SERVICE:
            if action.target_service == "payment-service":
                # This resets the circuit breaker
                new_state["circuit_breakers"]["payment-service"] = "CLOSED"
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="payment-service",
                    level=LogLevel.INFO,
                    message="Service restarted. Circuit breaker reset to CLOSED state.",
                ))

                # If nginx is already fixed, this completes the resolution
                if nginx_fixed:
                    self._fix_all_services(new_state, effects)
                else:
                    # Circuit breaker will trip again soon because nginx is still broken
                    effects["new_logs"].append(LogLine(
                        timestamp=self._format_timestamp(minutes_ago=0),
                        service="payment-service",
                        level=LogLevel.WARN,
                        message="Warning: Circuit breaker may trip again if upstream timeouts persist",
                    ))

        elif action.action_type == ActionType.SCALE_UP:
            if action.target_service in ["payment-service", "nginx-ingress"]:
                # This makes the retry storm WORSE
                effects["catastrophic"] = True
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service=action.target_service,
                    level=LogLevel.ERROR,
                    message="CRITICAL: Scaling up amplified retry storm! Error rate increasing.",
                ))
                # Degrade more services
                new_state["metrics"]["api-gateway"]["error_rate_pct"] = 50.0
                new_state["metrics"]["api-gateway"]["status"] = ServiceStatus.DOWN.value
                effects["services_degraded"].append("api-gateway")

        elif action.action_type == ActionType.ACKNOWLEDGE_ALERT:
            if action.target_service == "notification-service":
                # Correct - this is a separate issue
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="notification-service",
                    level=LogLevel.INFO,
                    message="Alert acknowledged. Queue backlog is a separate issue - tracking separately.",
                ))

        return new_state, effects

    def _fix_all_services(self, state: dict[str, Any], effects: dict[str, Any]) -> None:
        """Fix all affected services when both root causes are addressed"""
        state["metrics"]["nginx-ingress"] = self.create_healthy_metrics("nginx-ingress").model_dump()
        state["metrics"]["payment-service"] = self.create_healthy_metrics("payment-service").model_dump()
        state["metrics"]["api-gateway"] = self.create_healthy_metrics("api-gateway").model_dump()

        effects["services_fixed"] = ["nginx-ingress", "payment-service", "api-gateway"]
        effects["root_cause_addressed"] = True

        effects["new_logs"].append(LogLine(
            timestamp=self._format_timestamp(minutes_ago=0),
            service="payment-service",
            level=LogLevel.INFO,
            message="All services recovered. Retry storm subsided. Circuit breakers stable.",
        ))

    def is_resolved(self, state: dict[str, Any]) -> bool:
        """Check if incident is fully resolved"""
        # nginx-ingress and payment-service must be healthy
        # notification-service is a separate issue - does not need to be fixed
        required_services = ["nginx-ingress", "payment-service", "api-gateway"]

        for service in required_services:
            metrics = state.get("metrics", {}).get(service, {})
            if metrics.get("status") != ServiceStatus.HEALTHY.value:
                return False

        # Check root causes addressed
        nginx_fixed = state.get("config_changes", {}).get("nginx-ingress", {}).get("timeout_ms", 100) == 5000
        circuit_breaker_reset = state.get("circuit_breakers", {}).get("payment-service") == "CLOSED"

        return nginx_fixed and circuit_breaker_reset
