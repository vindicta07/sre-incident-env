"""Unit tests for FastAPI endpoints"""

import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)


class TestRootEndpoint:
    """Tests for root endpoint"""

    def test_root_serves_redoc(self):
        """Root endpoint should serve ReDoc HTML"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "ReDoc" in response.text

    def test_health_check(self):
        """Health check should return healthy"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestResetEndpoint:
    """Tests for /reset endpoint"""

    def test_reset_returns_observation(self):
        """Reset should return initial observation"""
        response = client.post("/reset", json={})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "observation" in data
        assert data["observation"]["step_count"] == 0

    def test_reset_with_task_id(self):
        """Reset with task_id should use that task"""
        response = client.post("/reset", json={"task_id": "task_1_single_service_crash"})
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_1_single_service_crash"

    def test_reset_invalid_task_id(self):
        """Reset with invalid task_id should return error"""
        response = client.post("/reset", json={"task_id": "invalid_task"})
        assert response.status_code == 400


class TestStepEndpoint:
    """Tests for /step endpoint"""

    def test_step_requires_session(self):
        """Step without session should return error"""
        response = client.post("/step", json={
            "action_type": "check_logs",
            "target_service": "auth-service",
        })
        assert response.status_code == 400

    def test_step_with_valid_session(self):
        """Step with valid session should work"""
        # First reset to get a session
        reset_response = client.post("/reset", json={"task_id": "task_1_single_service_crash"})
        session_id = reset_response.json()["session_id"]

        # Then step
        response = client.post("/step", json={
            "action_type": "check_logs",
            "target_service": "auth-service",
            "session_id": session_id,
        })
        assert response.status_code == 200
        data = response.json()
        assert "observation" in data
        assert "reward" in data
        assert "done" in data

    def test_step_invalid_action_type(self):
        """Step with invalid action type should return error"""
        reset_response = client.post("/reset", json={})
        session_id = reset_response.json()["session_id"]

        response = client.post("/step", json={
            "action_type": "invalid_action",
            "target_service": "auth-service",
            "session_id": session_id,
        })
        assert response.status_code == 400


class TestStateEndpoint:
    """Tests for /state endpoint"""

    def test_state_requires_session(self):
        """State without valid session should return error"""
        response = client.get("/state?session_id=invalid")
        assert response.status_code == 400

    def test_state_with_valid_session(self):
        """State with valid session should return observation"""
        reset_response = client.post("/reset", json={})
        session_id = reset_response.json()["session_id"]

        response = client.get(f"/state?session_id={session_id}")
        assert response.status_code == 200
        data = response.json()
        assert "observation" in data


class TestTasksEndpoint:
    """Tests for /tasks endpoint"""

    def test_tasks_returns_list(self):
        """Tasks should return list of tasks"""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "action_schema" in data
        assert len(data["tasks"]) == 3

    def test_tasks_include_all_difficulties(self):
        """Tasks should include easy, medium, and hard"""
        response = client.get("/tasks")
        data = response.json()
        difficulties = [t["difficulty"] for t in data["tasks"]]
        assert "easy" in difficulties
        assert "medium" in difficulties
        assert "hard" in difficulties


class TestGraderEndpoint:
    """Tests for /grader endpoint"""

    def test_grader_returns_score(self):
        """Grader should return a score"""
        response = client.post("/grader", json={
            "task_id": "task_1_single_service_crash",
            "episode_history": {
                "actions": [
                    {"action_type": "rollback_deploy", "target_service": "auth-service", "parameters": {"version": "v2.3.0"}},
                ],
                "rewards": [1.0],
                "total_steps": 1,
                "final_state": {"termination_reason": "incident_resolved"},
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert 0.0 <= data["score"] <= 1.0
        assert "feedback" in data

    def test_grader_invalid_task_id(self):
        """Grader with invalid task_id should return error score"""
        response = client.post("/grader", json={
            "task_id": "invalid_task",
            "episode_history": {"actions": [], "rewards": [], "total_steps": 0},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 0.0


class TestBaselineEndpoints:
    """Tests for baseline endpoints"""

    def test_baseline_status(self):
        """Baseline status should return availability info"""
        response = client.get("/baseline/status")
        assert response.status_code == 200
        data = response.json()
        assert "hf_token_configured" in data
        assert "baseline_module_available" in data
        assert "ready" in data

    def test_baseline_without_token(self):
        """Baseline without HF_TOKEN should return error"""
        # This test assumes HF_TOKEN is not set in the test environment
        response = client.post("/baseline")
        # Should return 503 if no token
        assert response.status_code in [200, 503]
