"""Task 2: Database Cascade Failure Scenario (Medium)

Root Cause: Feature flag 'new_dashboard' enabled a full-table scan on 500M row users table
Solution: Kill slow queries + disable feature flag
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


class DatabaseCascadeScenario(BaseScenario):
    """Medium scenario: Database cascade failure due to feature flag"""

    def _create_config(self) -> ScenarioConfig:
        return ScenarioConfig(
            task_id="task_2_db_cascade_failure",
            name="Database Cascade Failure",
            difficulty="medium",
            description=(
                "Primary PostgreSQL is under extreme load due to a missing index on a hot query path "
                "(triggered by a new feature flag). This causes connection pool exhaustion, which "
                "cascades to user-service and order-service going down. Agent must trace the cascade, "
                "kill slow queries, and disable the feature flag."
            ),
            target_score="0.6-0.9",
            services_affected=["postgres-primary", "user-service", "order-service"],
            root_cause_services=["postgres-primary"],
            root_cause_description="Feature flag 'new_dashboard' enabled a full-table scan query on users table (500M rows)",
            noise_level="medium",
            red_herrings=[
                "order-service shows errors (cascaded, not root cause)",
                "A deploy happened 2 hours ago (unrelated)",
            ],
            optimal_actions=[
                {"action_type": "check_logs", "target_service": "postgres-primary"},
                {"action_type": "run_sql_query", "target_service": "postgres-primary"},
                {"action_type": "kill_slow_queries", "target_service": "postgres-primary"},
                {"action_type": "toggle_feature_flag", "target_service": "postgres-primary", "parameters": {"flag": "new_dashboard", "state": False}},
            ],
            catastrophic_actions=[
                {"action_type": "restart_service", "target_service": "postgres-primary"},
                {"action_type": "scale_down", "target_service": "postgres-primary"},
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
            "notification-service": ["redis-cache"],
        }

    def _get_initial_feature_flags(self) -> dict[str, bool]:
        return {
            "new_dashboard": True,  # This is the problematic flag
            "dark_mode": True,
            "beta_features": False,
        }

    def _get_initial_slow_queries(self) -> bool:
        return True

    def _generate_initial_metrics(self) -> dict[str, ServiceMetrics]:
        services = list(self._get_service_graph().keys())
        metrics = {}

        for service in services:
            if service == "postgres-primary":
                # Extreme load - connection pool exhausted
                metrics[service] = ServiceMetrics(
                    cpu_pct=99.2,
                    memory_pct=95.0,
                    error_rate_pct=45.0,
                    p99_latency_ms=15000.0,  # 15 seconds!
                    request_rate_rps=50.0,  # Very low due to blocked connections
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "user-service":
                # Down due to DB connection exhaustion
                metrics[service] = ServiceMetrics(
                    cpu_pct=15.0,  # Low CPU - just waiting on DB
                    memory_pct=80.0,  # High memory - holding blocked requests
                    error_rate_pct=100.0,
                    p99_latency_ms=30000.0,  # Timeout
                    request_rate_rps=0.0,
                    status=ServiceStatus.DOWN,
                )
            elif service == "order-service":
                # Degraded due to DB issues
                metrics[service] = ServiceMetrics(
                    cpu_pct=20.0,
                    memory_pct=70.0,
                    error_rate_pct=85.0,
                    p99_latency_ms=25000.0,
                    request_rate_rps=10.0,
                    status=ServiceStatus.DEGRADED,
                )
            elif service == "api-gateway":
                # Degraded due to downstream issues
                metrics[service] = ServiceMetrics(
                    cpu_pct=55.0,
                    memory_pct=60.0,
                    error_rate_pct=40.0,
                    p99_latency_ms=20000.0,
                    request_rate_rps=200.0,
                    status=ServiceStatus.DEGRADED,
                )
            else:
                metrics[service] = self.create_healthy_metrics(service)

        return metrics

    def _generate_initial_alerts(self) -> list[Alert]:
        return [
            Alert(
                service="postgres-primary",
                severity=Severity.P1,
                message="PostgreSQL connection pool exhausted - max_connections reached",
                fired_at=self._format_timestamp(minutes_ago=15),
                acknowledged=False,
            ),
            Alert(
                service="postgres-primary",
                severity=Severity.P1,
                message="Query latency > 10s detected on postgres-primary",
                fired_at=self._format_timestamp(minutes_ago=18),
                acknowledged=False,
            ),
            Alert(
                service="user-service",
                severity=Severity.P1,
                message="user-service is DOWN - cannot connect to database",
                fired_at=self._format_timestamp(minutes_ago=12),
                acknowledged=False,
            ),
            Alert(
                service="order-service",
                severity=Severity.P2,
                message="order-service error rate > 80%",
                fired_at=self._format_timestamp(minutes_ago=10),
                acknowledged=False,
            ),
            Alert(
                service="api-gateway",
                severity=Severity.P2,
                message="Overall system error rate elevated",
                fired_at=self._format_timestamp(minutes_ago=8),
                acknowledged=False,
            ),
        ]

    def _generate_initial_logs(self) -> list[LogLine]:
        return [
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=20),
                service="postgres-primary",
                level=LogLevel.WARN,
                message="Slow query detected: SELECT * FROM users WHERE dashboard_enabled = true (running for 45s)",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=19),
                service="postgres-primary",
                level=LogLevel.WARN,
                message="Connection pool usage at 90% (180/200 connections)",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=18),
                service="postgres-primary",
                level=LogLevel.ERROR,
                message="Connection pool exhausted - rejecting new connections",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=17),
                service="user-service",
                level=LogLevel.ERROR,
                message="Failed to acquire database connection after 30s timeout",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=16),
                service="user-service",
                level=LogLevel.FATAL,
                message="Database connection pool exhausted - service unhealthy",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=15),
                service="order-service",
                level=LogLevel.ERROR,
                message="Intermittent database connection failures",
            ),
            LogLine(
                timestamp=self._format_timestamp(minutes_ago=10),
                service="order-service",
                level=LogLevel.WARN,
                message="Retrying failed database operations (attempt 3/5)",
            ),
        ]

    def _generate_deploys(self) -> list[Deploy]:
        return [
            Deploy(
                service="notification-service",
                version="v1.5.0",
                deployed_at=self._format_timestamp(minutes_ago=120),  # 2 hours ago - red herring
                deployed_by="charlie@company.com",
                is_rollback_target=True,
            ),
            Deploy(
                service="user-service",
                version="v3.2.1",
                deployed_at=self._format_timestamp(minutes_ago=1440),  # 24 hours ago
                deployed_by="alice@company.com",
                is_rollback_target=True,
            ),
        ]

    def get_check_logs_result(self, service: str) -> list[LogLine]:
        """Get detailed logs when agent checks logs on a service"""
        if service == "postgres-primary":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=25),
                    service="postgres-primary",
                    level=LogLevel.INFO,
                    message="Feature flag 'new_dashboard' enabled at 14:35:00 UTC",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=24),
                    service="postgres-primary",
                    level=LogLevel.INFO,
                    message="New query pattern detected: SELECT * FROM users WHERE dashboard_enabled = true",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=23),
                    service="postgres-primary",
                    level=LogLevel.WARN,
                    message="Query execution time: 45.2s - missing index on dashboard_enabled column",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=22),
                    service="postgres-primary",
                    level=LogLevel.WARN,
                    message="Sequential scan on users table (500,000,000 rows) - extremely slow",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=20),
                    service="postgres-primary",
                    level=LogLevel.ERROR,
                    message="Long-running queries blocking connection pool: 45 queries waiting",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=18),
                    service="postgres-primary",
                    level=LogLevel.FATAL,
                    message="CRITICAL: Connection pool at 100% - 200/200 connections in use",
                ),
            ]
        elif service == "user-service":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=17),
                    service="user-service",
                    level=LogLevel.ERROR,
                    message="Cannot acquire database connection from pool",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=16),
                    service="user-service",
                    level=LogLevel.ERROR,
                    message="Health check failed: database unreachable",
                ),
            ]
        elif service == "order-service":
            return [
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=15),
                    service="order-service",
                    level=LogLevel.WARN,
                    message="Database queries timing out intermittently",
                ),
                LogLine(
                    timestamp=self._format_timestamp(minutes_ago=12),
                    service="order-service",
                    level=LogLevel.ERROR,
                    message="Failed to commit transaction - connection lost",
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
        if "feature_flags" not in new_state:
            new_state["feature_flags"] = self._get_initial_feature_flags()
        if "slow_queries_active" not in new_state:
            new_state["slow_queries_active"] = True

        effects = {
            "services_fixed": [],
            "services_degraded": [],
            "root_cause_addressed": False,
            "catastrophic": False,
            "new_logs": [],
        }

        slow_queries_killed = not new_state.get("slow_queries_active", True)
        flag_disabled = not new_state.get("feature_flags", {}).get("new_dashboard", True)

        if action.action_type == ActionType.KILL_SLOW_QUERIES:
            if action.target_service == "postgres-primary":
                new_state["slow_queries_active"] = False
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="postgres-primary",
                    level=LogLevel.INFO,
                    message="Killed 45 long-running queries. Connection pool usage dropping.",
                ))

                # If flag is already disabled, this fixes things
                if flag_disabled:
                    self._fix_all_services(new_state, effects)

        elif action.action_type == ActionType.TOGGLE_FEATURE_FLAG:
            params = action.parameters or {}
            flag_name = params.get("flag", "new_dashboard")
            flag_state = params.get("state", False)

            if flag_name == "new_dashboard" and not flag_state:
                new_state["feature_flags"]["new_dashboard"] = False
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="postgres-primary",
                    level=LogLevel.INFO,
                    message="Feature flag 'new_dashboard' disabled. No new slow queries will be generated.",
                ))

                # If slow queries already killed, this fixes things
                if slow_queries_killed:
                    self._fix_all_services(new_state, effects)
                else:
                    # Partial fix - new queries stopped but existing ones still running
                    effects["new_logs"].append(LogLine(
                        timestamp=self._format_timestamp(minutes_ago=0),
                        service="postgres-primary",
                        level=LogLevel.WARN,
                        message="Existing slow queries still running. Consider killing them.",
                    ))

        elif action.action_type == ActionType.RESTART_SERVICE:
            if action.target_service == "postgres-primary":
                # This is catastrophic during write-heavy load!
                effects["catastrophic"] = True
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service="postgres-primary",
                    level=LogLevel.FATAL,
                    message="CRITICAL: Database restart during active transactions - potential data loss!",
                ))
            elif action.target_service in ["user-service", "order-service"]:
                # Restarting downstream services doesn't help
                effects["new_logs"].append(LogLine(
                    timestamp=self._format_timestamp(minutes_ago=0),
                    service=action.target_service,
                    level=LogLevel.WARN,
                    message="Service restarted but still cannot connect to database",
                ))

        elif action.action_type == ActionType.SCALE_DOWN:
            if action.target_service == "postgres-primary":
                effects["catastrophic"] = True

        elif action.action_type == ActionType.RUN_SQL_QUERY:
            # Informational - shows top slow queries
            effects["new_logs"].append(LogLine(
                timestamp=self._format_timestamp(minutes_ago=0),
                service="postgres-primary",
                level=LogLevel.INFO,
                message="Top slow queries: 1) SELECT * FROM users WHERE dashboard_enabled=true (45s, triggered by new_dashboard flag)",
            ))

        return new_state, effects

    def _fix_all_services(self, state: dict[str, Any], effects: dict[str, Any]) -> None:
        """Fix all affected services when root cause is addressed"""
        state["metrics"]["postgres-primary"] = self.create_healthy_metrics("postgres-primary").model_dump()
        state["metrics"]["user-service"] = self.create_healthy_metrics("user-service").model_dump()
        state["metrics"]["order-service"] = self.create_healthy_metrics("order-service").model_dump()
        state["metrics"]["api-gateway"] = self.create_healthy_metrics("api-gateway").model_dump()

        effects["services_fixed"] = ["postgres-primary", "user-service", "order-service", "api-gateway"]
        effects["root_cause_addressed"] = True

        effects["new_logs"].append(LogLine(
            timestamp=self._format_timestamp(minutes_ago=0),
            service="postgres-primary",
            level=LogLevel.INFO,
            message="Connection pool usage normalized. All services recovering.",
        ))

    def is_resolved(self, state: dict[str, Any]) -> bool:
        """Check if incident is fully resolved"""
        required_services = ["postgres-primary", "user-service", "order-service"]

        for service in required_services:
            metrics = state.get("metrics", {}).get(service, {})
            if metrics.get("status") != ServiceStatus.HEALTHY.value:
                return False

        # Also check that root cause is addressed
        slow_queries_killed = not state.get("slow_queries_active", True)
        flag_disabled = not state.get("feature_flags", {}).get("new_dashboard", True)

        return slow_queries_killed and flag_disabled
