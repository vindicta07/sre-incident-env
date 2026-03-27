"""Compatibility client helpers for OpenEnv-style project layout."""

from __future__ import annotations

from typing import Any

import httpx


class SREIncidentEnvClient:
    """Small HTTP client for interacting with the deployed environment."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=60.0)

    def reset(self, task_id: str | None = None) -> dict[str, Any]:
        payload = {"task_id": task_id} if task_id else {}
        response = self._client.post("/reset", json=payload)
        response.raise_for_status()
        return response.json()

    def step(
        self,
        action_type: str,
        target_service: str,
        session_id: str,
        parameters: dict[str, Any] | None = None,
        reasoning: str = "",
    ) -> dict[str, Any]:
        payload = {
            "action_type": action_type,
            "target_service": target_service,
            "session_id": session_id,
            "parameters": parameters,
            "reasoning": reasoning,
        }
        response = self._client.post("/step", json=payload)
        response.raise_for_status()
        return response.json()

    def state(self, session_id: str) -> dict[str, Any]:
        response = self._client.get("/state", params={"session_id": session_id})
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
