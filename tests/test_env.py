"""Unit tests for SRE Incident Environment"""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment import SREIncidentEnv
from environment.models import SREAction, ActionType, ServiceStatus


class TestEnvironmentReset:
    """Tests for environment reset functionality"""

    def test_reset_random_task(self):
        """Reset with no task_id should select a random task"""
        env = SREIncidentEnv()
        obs = env.reset()

        assert obs is not None
        assert obs.incident_id is not None
        assert len(obs.incident_id) > 0
        assert obs.step_count == 0
        assert obs.elapsed_sim_minutes == 0

    def test_reset_specific_task(self):
        """Reset with specific task_id should use that task"""
        env = SREIncidentEnv()
        obs = env.reset(task_id="task_1_single_service_crash")

        assert obs is not None
        assert env.scenario.task_id == "task_1_single_service_crash"

    def test_reset_invalid_task(self):
        """Reset with invalid task_id should raise error"""
        env = SREIncidentEnv()

        with pytest.raises(ValueError):
            env.reset(task_id="invalid_task")

    def test_reset_clears_previous_state(self):
        """Reset should clear state from previous episode"""
        env = SREIncidentEnv()
        obs1 = env.reset(task_id="task_1_single_service_crash")

        # Take some actions
        action = SREAction(
            action_type=ActionType.CHECK_LOGS,
            target_service="auth-service",
        )
        env.step(action)

        # Reset
        obs2 = env.reset(task_id="task_2_db_cascade_failure")

        assert obs2.step_count == 0
        assert len(obs2.action_history) == 0


class TestEnvironmentStep:
    """Tests for environment step functionality"""

    def test_step_increments_count(self):
        """Step should increment step count"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        action = SREAction(
            action_type=ActionType.CHECK_LOGS,
            target_service="auth-service",
        )
        result = env.step(action)

        assert result.observation.step_count == 1

    def test_step_returns_reward(self):
        """Step should return a reward"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        action = SREAction(
            action_type=ActionType.CHECK_LOGS,
            target_service="auth-service",
            reasoning="Checking auth-service logs to diagnose the issue",
        )
        result = env.step(action)

        assert isinstance(result.reward, float)

    def test_step_updates_action_history(self):
        """Step should add action to history"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        action = SREAction(
            action_type=ActionType.CHECK_LOGS,
            target_service="auth-service",
        )
        result = env.step(action)

        assert len(result.observation.action_history) == 1

    def test_step_without_reset_raises_error(self):
        """Step without reset should raise error"""
        env = SREIncidentEnv()

        action = SREAction(
            action_type=ActionType.CHECK_LOGS,
            target_service="auth-service",
        )

        with pytest.raises(RuntimeError):
            env.step(action)

    def test_step_after_done_raises_error(self):
        """Step after episode is done should raise error"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        # Resolve the incident
        action = SREAction(
            action_type=ActionType.ROLLBACK_DEPLOY,
            target_service="auth-service",
            parameters={"version": "v2.3.0"},
        )
        result = env.step(action)

        # If resolved or max steps, should be done
        if result.done:
            with pytest.raises(RuntimeError):
                env.step(action)

    def test_max_steps_terminates(self):
        """Episode should terminate after max steps"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        action = SREAction(
            action_type=ActionType.NOOP,
            target_service="auth-service",
        )

        # Take max steps
        for _ in range(20):
            result = env.step(action)
            if result.done:
                break

        assert env.done
        assert env.termination_reason in ["max_steps_reached", "incident_resolved", "catastrophic_action_taken"]


class TestEnvironmentState:
    """Tests for environment state functionality"""

    def test_state_returns_current_observation(self):
        """State should return current observation"""
        env = SREIncidentEnv()
        obs = env.reset(task_id="task_1_single_service_crash")
        state = env.state()

        assert state.incident_id == obs.incident_id

    def test_state_without_reset_raises_error(self):
        """State without reset should raise error"""
        env = SREIncidentEnv()

        with pytest.raises(RuntimeError):
            env.state()


class TestTask1SingleServiceCrash:
    """Tests specific to Task 1: Single Service Crash"""

    def test_auth_service_is_down(self):
        """Auth service should be down initially"""
        env = SREIncidentEnv()
        obs = env.reset(task_id="task_1_single_service_crash")

        auth_metrics = obs.metrics.get("auth-service")
        assert auth_metrics is not None
        assert auth_metrics.status == ServiceStatus.DOWN
        assert auth_metrics.error_rate_pct == 100.0

    def test_rollback_fixes_auth_service(self):
        """Rolling back auth-service should fix the incident"""
        env = SREIncidentEnv()
        env.reset(task_id="task_1_single_service_crash")

        action = SREAction(
            action_type=ActionType.ROLLBACK_DEPLOY,
            target_service="auth-service",
            parameters={"version": "v2.3.0"},
            reasoning="Rolling back bad deploy",
        )
        result = env.step(action)

        # Check if resolved
        auth_metrics = result.observation.metrics.get("auth-service")
        assert auth_metrics.status == ServiceStatus.HEALTHY


class TestTask2DatabaseCascade:
    """Tests specific to Task 2: Database Cascade Failure"""

    def test_postgres_is_degraded(self):
        """Postgres should be degraded initially"""
        env = SREIncidentEnv()
        obs = env.reset(task_id="task_2_db_cascade_failure")

        pg_metrics = obs.metrics.get("postgres-primary")
        assert pg_metrics is not None
        assert pg_metrics.status == ServiceStatus.DEGRADED
        assert pg_metrics.cpu_pct > 90

    def test_kill_queries_and_flag_fixes_incident(self):
        """Killing queries and disabling flag should fix incident"""
        env = SREIncidentEnv()
        env.reset(task_id="task_2_db_cascade_failure")

        # Kill slow queries
        action1 = SREAction(
            action_type=ActionType.KILL_SLOW_QUERIES,
            target_service="postgres-primary",
        )
        env.step(action1)

        # Disable feature flag
        action2 = SREAction(
            action_type=ActionType.TOGGLE_FEATURE_FLAG,
            target_service="postgres-primary",
            parameters={"flag": "new_dashboard", "state": False},
        )
        result = env.step(action2)

        # Should be resolved
        assert result.done or result.observation.metrics.get("postgres-primary").status == ServiceStatus.HEALTHY


class TestTask3DistributedGhost:
    """Tests specific to Task 3: Distributed Ghost Incident"""

    def test_nginx_and_payment_affected(self):
        """Nginx and payment service should be affected"""
        env = SREIncidentEnv()
        obs = env.reset(task_id="task_3_distributed_ghost_incident")

        nginx_metrics = obs.metrics.get("nginx-ingress")
        payment_metrics = obs.metrics.get("payment-service")

        assert nginx_metrics.status == ServiceStatus.DEGRADED
        assert payment_metrics.status == ServiceStatus.DEGRADED

    def test_scale_up_is_catastrophic(self):
        """Scaling up during retry storm should be catastrophic"""
        env = SREIncidentEnv()
        env.reset(task_id="task_3_distributed_ghost_incident")

        action = SREAction(
            action_type=ActionType.SCALE_UP,
            target_service="payment-service",
            parameters={"replicas": 5},
        )
        result = env.step(action)

        # Should trigger catastrophic termination
        assert result.done
        assert env.termination_reason == "catastrophic_action_taken"
