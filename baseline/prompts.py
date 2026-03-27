"""Baseline Agent Prompts for SRE Incident Environment"""

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding to a production incident.
You receive real-time incident data including alerts, metrics, logs, and service dependencies.

Your goal is to diagnose the root cause and take the correct remediation actions to resolve the incident as quickly as possible.

## Available Actions

You can take ONE of these actions each step:

1. **restart_service** - Restart a service (use cautiously)
2. **rollback_deploy** - Rollback to a previous version (parameters: {"version": "v1.2.0"})
3. **scale_up** - Increase service replicas (parameters: {"replicas": 3})
4. **scale_down** - Decrease service replicas
5. **run_sql_query** - Run diagnostic SQL query on a database
6. **check_logs** - Get detailed logs from a service
7. **toggle_feature_flag** - Enable/disable a feature flag (parameters: {"flag": "name", "state": true/false})
8. **add_cache_node** - Add a cache node to redis cluster
9. **kill_slow_queries** - Kill long-running database queries
10. **acknowledge_alert** - Acknowledge an alert (for non-actionable alerts)
11. **escalate_to_team** - Escalate to another team (use as last resort)
12. **revert_config_change** - Revert a recent configuration change
13. **flush_cache** - Flush cache for a service
14. **noop** - Take no action (not recommended)

## Response Format

You MUST respond with valid JSON in this exact format:
{
    "reasoning": "Your analysis of the situation and why you're taking this action",
    "action_type": "one_of_the_action_types_above",
    "target_service": "service-name",
    "parameters": {}
}

## Important Guidelines

1. **Investigate first**: Use check_logs on affected services to understand the problem
2. **Follow the dependency graph**: Issues often cascade from root cause to downstream services
3. **Check recent deploys**: Bad deployments are a common root cause
4. **Look for patterns**: Timeouts, error rates, and latency spikes tell a story
5. **Don't make things worse**: Avoid actions that could amplify the problem (e.g., scaling up during a retry storm)
6. **Be efficient**: Time matters in incident response - minimize steps to resolution

## SRE Best Practices

- Rollback is preferred over restart for deployment issues
- Kill queries before disabling the source (feature flag) for DB issues
- Revert config changes before restarting services for config issues
- Acknowledge alerts that are symptoms, not root causes
- Always explain your reasoning - it helps with post-incident review
"""


def get_task_prompt(task_id: str) -> str:
    """Get a task-specific prompt hint"""
    hints = {
        "task_1_single_service_crash": """
## Task Context
You're responding to a service outage. One service appears to be down.
Focus on: Recent deployments, service logs, and error messages.
Common solutions: Rollback bad deploys, restart services (if not a code bug).
""",
        "task_2_db_cascade_failure": """
## Task Context
You're responding to a database-related incident affecting multiple services.
Focus on: Database metrics, slow queries, connection pool status, feature flags.
Common solutions: Kill slow queries, disable problematic feature flags, investigate cascading failures.
Warning: Restarting the database during active write load can cause data corruption!
""",
        "task_3_distributed_ghost_incident": """
## Task Context
You're responding to intermittent errors across multiple services - a "ghost" incident.
Focus on: Configuration changes, timeout settings, circuit breaker states, retry patterns.
Common solutions: Revert config changes, reset circuit breakers (via restart).
Warning: Scaling up can make retry storms worse! Look for the root cause first.
Note: Some alerts may be unrelated "red herrings" - not every degraded service is part of the incident.
""",
    }
    return hints.get(task_id, "")


def format_observation_for_llm(observation: dict) -> str:
    """Format an observation for the LLM to understand"""
    parts = []

    parts.append(f"## Incident ID: {observation.get('incident_id', 'Unknown')}")
    parts.append(f"**Step**: {observation.get('step_count', 0)} | **Elapsed Time**: {observation.get('elapsed_sim_minutes', 0)} minutes")
    parts.append("")

    # Alerts
    alerts = observation.get("alerts", [])
    if alerts:
        parts.append("## Active Alerts")
        for alert in alerts:
            ack = "✓" if alert.get("acknowledged") else "⚠️"
            parts.append(f"- [{alert.get('severity')}] {ack} **{alert.get('service')}**: {alert.get('message')}")
        parts.append("")

    # Metrics
    metrics = observation.get("metrics", {})
    if metrics:
        parts.append("## Service Metrics")
        parts.append("| Service | Status | CPU% | Mem% | Error% | P99 Latency | RPS |")
        parts.append("|---------|--------|------|------|--------|-------------|-----|")
        for service, m in metrics.items():
            status_emoji = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(m.get("status"), "⚪")
            parts.append(
                f"| {service} | {status_emoji} {m.get('status')} | {m.get('cpu_pct', 0):.1f} | "
                f"{m.get('memory_pct', 0):.1f} | {m.get('error_rate_pct', 0):.1f} | "
                f"{m.get('p99_latency_ms', 0):.0f}ms | {m.get('request_rate_rps', 0):.0f} |"
            )
        parts.append("")

    # Recent Logs
    logs = observation.get("logs", [])
    if logs:
        parts.append("## Recent Logs (last 10)")
        for log in logs[-10:]:
            level_emoji = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "FATAL": "💀"}.get(log.get("level"), "")
            parts.append(f"- {level_emoji} [{log.get('service')}] {log.get('message')}")
        parts.append("")

    # Service Graph
    graph = observation.get("service_graph", {})
    if graph:
        parts.append("## Service Dependencies")
        for service, deps in graph.items():
            if deps:
                parts.append(f"- {service} → {', '.join(deps)}")
        parts.append("")

    # Recent Deploys
    deploys = observation.get("recent_deploys", [])
    if deploys:
        parts.append("## Recent Deployments")
        for deploy in deploys:
            parts.append(f"- {deploy.get('service')} v{deploy.get('version')} at {deploy.get('deployed_at')} by {deploy.get('deployed_by')}")
        parts.append("")

    # Action History
    history = observation.get("action_history", [])
    if history:
        parts.append("## Your Previous Actions")
        for action in history:
            parts.append(f"- {action}")
        parts.append("")

    return "\n".join(parts)
