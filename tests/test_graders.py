"""Unit tests for Graders"""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment.models import EpisodeHistory, SREAction, ActionType
from graders import grade_episode, Task1Grader, Task2Grader, Task3Grader


class TestTask1Grader:
    """Tests for Task 1 grader"""

    def test_perfect_score_rollback_fast(self):
        """Rollback in ≤3 steps should get 1.0"""
        history = EpisodeHistory(
            task_id="task_1_single_service_crash",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="auth-service"),
                SREAction(action_type=ActionType.ROLLBACK_DEPLOY, target_service="auth-service", parameters={"version": "v2.3.0"}),
            ],
            total_steps=2,
            final_state={"termination_reason": "incident_resolved"},
        )

        result = grade_episode("task_1_single_service_crash", history)
        assert result.score == 1.0

    def test_good_score_rollback_slow(self):
        """Rollback in 4-6 steps should get 0.7"""
        history = EpisodeHistory(
            task_id="task_1_single_service_crash",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="api-gateway"),
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="user-service"),
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="auth-service"),
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="auth-service"),
                SREAction(action_type=ActionType.ROLLBACK_DEPLOY, target_service="auth-service", parameters={"version": "v2.3.0"}),
            ],
            total_steps=5,
            final_state={"termination_reason": "incident_resolved"},
        )

        result = grade_episode("task_1_single_service_crash", history)
        assert result.score == 0.7

    def test_zero_score_never_targeted(self):
        """Never targeting auth-service should get 0.0"""
        history = EpisodeHistory(
            task_id="task_1_single_service_crash",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="api-gateway"),
                SREAction(action_type=ActionType.RESTART_SERVICE, target_service="api-gateway"),
            ],
            total_steps=2,
            final_state={"termination_reason": "max_steps_reached"},
        )

        result = grade_episode("task_1_single_service_crash", history)
        assert result.score == 0.0

    def test_catastrophic_action_zero(self):
        """Catastrophic action should get 0.0"""
        history = EpisodeHistory(
            task_id="task_1_single_service_crash",
            actions=[
                SREAction(action_type=ActionType.SCALE_DOWN, target_service="auth-service"),
            ],
            total_steps=1,
            final_state={"termination_reason": "catastrophic_action_taken"},
        )

        result = grade_episode("task_1_single_service_crash", history)
        assert result.score == 0.0


class TestTask2Grader:
    """Tests for Task 2 grader"""

    def test_perfect_score_full_sequence(self):
        """Full correct sequence should get 1.0"""
        history = EpisodeHistory(
            task_id="task_2_db_cascade_failure",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="postgres-primary"),
                SREAction(action_type=ActionType.RUN_SQL_QUERY, target_service="postgres-primary"),
                SREAction(action_type=ActionType.KILL_SLOW_QUERIES, target_service="postgres-primary"),
                SREAction(action_type=ActionType.TOGGLE_FEATURE_FLAG, target_service="postgres-primary", parameters={"flag": "new_dashboard", "state": False}),
            ],
            total_steps=4,
            final_state={"termination_reason": "incident_resolved"},
        )

        result = grade_episode("task_2_db_cascade_failure", history)
        assert result.score == 1.0

    def test_partial_score_flag_only(self):
        """Disabling flag only should get 0.6"""
        history = EpisodeHistory(
            task_id="task_2_db_cascade_failure",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="postgres-primary"),
                SREAction(action_type=ActionType.TOGGLE_FEATURE_FLAG, target_service="postgres-primary", parameters={"flag": "new_dashboard", "state": False}),
            ],
            total_steps=2,
            final_state={"termination_reason": "max_steps_reached"},
        )

        result = grade_episode("task_2_db_cascade_failure", history)
        assert result.score == 0.6

    def test_escalation_without_trying_zero(self):
        """Escalating without attempting resolution should get 0.0"""
        history = EpisodeHistory(
            task_id="task_2_db_cascade_failure",
            actions=[
                SREAction(action_type=ActionType.ESCALATE_TO_TEAM, target_service="on-call"),
            ],
            total_steps=1,
            final_state={"termination_reason": "max_steps_reached"},
        )

        result = grade_episode("task_2_db_cascade_failure", history)
        assert result.score == 0.0


class TestTask3Grader:
    """Tests for Task 3 grader"""

    def test_perfect_score_correct_order(self):
        """Nginx revert then payment restart in ≤6 steps should get 1.0"""
        history = EpisodeHistory(
            task_id="task_3_distributed_ghost_incident",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="nginx-ingress"),
                SREAction(action_type=ActionType.REVERT_CONFIG_CHANGE, target_service="nginx-ingress"),
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="payment-service"),
                SREAction(action_type=ActionType.RESTART_SERVICE, target_service="payment-service"),
            ],
            total_steps=4,
            final_state={"termination_reason": "incident_resolved"},
        )

        result = grade_episode("task_3_distributed_ghost_incident", history)
        assert result.score == 1.0

    def test_partial_nginx_only(self):
        """Fixing nginx only should get 0.6"""
        history = EpisodeHistory(
            task_id="task_3_distributed_ghost_incident",
            actions=[
                SREAction(action_type=ActionType.CHECK_LOGS, target_service="nginx-ingress"),
                SREAction(action_type=ActionType.REVERT_CONFIG_CHANGE, target_service="nginx-ingress"),
            ],
            total_steps=2,
            final_state={"termination_reason": "max_steps_reached"},
        )

        result = grade_episode("task_3_distributed_ghost_incident", history)
        assert result.score == 0.6

    def test_scale_up_catastrophic_zero(self):
        """Scaling up during retry storm should get 0.0"""
        history = EpisodeHistory(
            task_id="task_3_distributed_ghost_incident",
            actions=[
                SREAction(action_type=ActionType.SCALE_UP, target_service="payment-service", parameters={"replicas": 5}),
            ],
            total_steps=1,
            final_state={"termination_reason": "catastrophic_action_taken"},
        )

        result = grade_episode("task_3_distributed_ghost_incident", history)
        assert result.score == 0.0


class TestGraderDeterminism:
    """Tests to verify graders are deterministic"""

    def test_task1_deterministic(self):
        """Task 1 grading should be deterministic"""
        history = EpisodeHistory(
            task_id="task_1_single_service_crash",
            actions=[
                SREAction(action_type=ActionType.ROLLBACK_DEPLOY, target_service="auth-service"),
            ],
            total_steps=1,
            final_state={"termination_reason": "incident_resolved"},
        )

        results = [grade_episode("task_1_single_service_crash", history) for _ in range(5)]
        scores = [r.score for r in results]

        assert all(s == scores[0] for s in scores)

    def test_task2_deterministic(self):
        """Task 2 grading should be deterministic"""
        history = EpisodeHistory(
            task_id="task_2_db_cascade_failure",
            actions=[
                SREAction(action_type=ActionType.KILL_SLOW_QUERIES, target_service="postgres-primary"),
                SREAction(action_type=ActionType.TOGGLE_FEATURE_FLAG, target_service="postgres-primary", parameters={"flag": "new_dashboard", "state": False}),
            ],
            total_steps=2,
            final_state={"termination_reason": "incident_resolved"},
        )

        results = [grade_episode("task_2_db_cascade_failure", history) for _ in range(5)]
        scores = [r.score for r in results]

        assert all(s == scores[0] for s in scores)

    def test_task3_deterministic(self):
        """Task 3 grading should be deterministic"""
        history = EpisodeHistory(
            task_id="task_3_distributed_ghost_incident",
            actions=[
                SREAction(action_type=ActionType.REVERT_CONFIG_CHANGE, target_service="nginx-ingress"),
                SREAction(action_type=ActionType.RESTART_SERVICE, target_service="payment-service"),
            ],
            total_steps=2,
            final_state={"termination_reason": "incident_resolved"},
        )

        results = [grade_episode("task_3_distributed_ghost_incident", history) for _ in range(5)]
        scores = [r.score for r in results]

        assert all(s == scores[0] for s in scores)
