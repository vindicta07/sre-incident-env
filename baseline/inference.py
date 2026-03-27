"""Baseline Agent using HuggingFace Inference API"""

import json
import os
import re
from typing import Any, Optional

import httpx

from environment import SREIncidentEnv
from environment.models import SREAction, ActionType
from graders import grade_episode
from .prompts import SYSTEM_PROMPT, get_task_prompt, format_observation_for_llm


class BaselineAgent:
    """
    Baseline agent using HuggingFace Inference API.

    Uses a ReAct-style prompting approach where the agent
    reasons about the situation before taking an action.
    """

    # HuggingFace model to use (Mixtral is a good balance of capability and cost)
    DEFAULT_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"

    def __init__(
        self,
        hf_token: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        if not self.hf_token:
            raise ValueError("HF_TOKEN is required for baseline agent")

        self.model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model}"

    def _call_hf_api(self, prompt: str) -> str:
        """Call HuggingFace Inference API"""
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 500,
                "temperature": 0.3,
                "top_p": 0.9,
                "do_sample": True,
                "return_full_text": False,
            },
        }

        for attempt in range(self.max_retries):
            try:
                response = httpx.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()

                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "")
                return str(result)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    # Model is loading, wait and retry
                    import time
                    time.sleep(20)
                    continue
                raise
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                import time
                time.sleep(5)

        raise RuntimeError("Max retries exceeded for HuggingFace API")

    def _parse_action(self, response: str) -> SREAction:
        """Parse LLM response into an SREAction"""
        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)

        if json_match:
            try:
                data = json.loads(json_match.group())

                # Validate action type
                action_type_str = data.get("action_type", "noop")
                try:
                    action_type = ActionType(action_type_str)
                except ValueError:
                    action_type = ActionType.NOOP

                return SREAction(
                    action_type=action_type,
                    target_service=data.get("target_service", "unknown"),
                    parameters=data.get("parameters"),
                    reasoning=data.get("reasoning", response[:200]),
                )

            except json.JSONDecodeError:
                pass

        # Fallback: try to extract action from text
        response_lower = response.lower()

        # Look for action keywords
        action_mapping = {
            "rollback": ActionType.ROLLBACK_DEPLOY,
            "restart": ActionType.RESTART_SERVICE,
            "check_logs": ActionType.CHECK_LOGS,
            "check logs": ActionType.CHECK_LOGS,
            "kill_slow_queries": ActionType.KILL_SLOW_QUERIES,
            "kill slow queries": ActionType.KILL_SLOW_QUERIES,
            "toggle_feature_flag": ActionType.TOGGLE_FEATURE_FLAG,
            "feature flag": ActionType.TOGGLE_FEATURE_FLAG,
            "revert_config": ActionType.REVERT_CONFIG_CHANGE,
            "revert config": ActionType.REVERT_CONFIG_CHANGE,
            "scale_up": ActionType.SCALE_UP,
            "scale up": ActionType.SCALE_UP,
        }

        detected_action = ActionType.NOOP
        for keyword, action in action_mapping.items():
            if keyword in response_lower:
                detected_action = action
                break

        # Try to find service name
        service = "unknown"
        common_services = [
            "auth-service", "api-gateway", "user-service", "order-service",
            "postgres-primary", "payment-service", "nginx-ingress",
            "notification-service", "redis-cache"
        ]
        for svc in common_services:
            if svc in response_lower:
                service = svc
                break

        return SREAction(
            action_type=detected_action,
            target_service=service,
            reasoning=response[:200],
        )

    def run_episode(self, task_id: str) -> dict[str, Any]:
        """Run a single episode and return the result"""
        env = SREIncidentEnv()
        observation = env.reset(task_id=task_id)

        total_reward = 0.0
        steps = 0

        while not env.done and steps < 20:
            # Format observation for LLM
            obs_text = format_observation_for_llm(observation.model_dump())

            # Build prompt
            prompt = f"""<s>[INST] {SYSTEM_PROMPT}

{get_task_prompt(task_id)}

## Current Situation

{obs_text}

Based on this information, what action should you take? Respond with JSON.
[/INST]"""

            # Get LLM response
            try:
                response = self._call_hf_api(prompt)
                action = self._parse_action(response)
            except Exception as e:
                # On error, take a safe action (check logs or noop)
                action = SREAction(
                    action_type=ActionType.CHECK_LOGS,
                    target_service="api-gateway",
                    reasoning=f"Error calling LLM: {str(e)}",
                )

            # Take step
            result = env.step(action)
            observation = result.observation
            total_reward += result.reward
            steps += 1

        # Grade the episode
        history = env.get_episode_history()
        grade_result = grade_episode(task_id, history)

        return {
            "task_id": task_id,
            "score": grade_result.score,
            "total_reward": total_reward,
            "steps": steps,
            "termination_reason": env.termination_reason,
            "feedback": grade_result.feedback,
        }

    def run_all_tasks(self) -> dict[str, Any]:
        """Run baseline on all tasks and return aggregate results"""
        task_ids = [
            "task_1_single_service_crash",
            "task_2_db_cascade_failure",
            "task_3_distributed_ghost_incident",
        ]

        results = {}
        scores = []

        for task_id in task_ids:
            try:
                result = self.run_episode(task_id)
                results[task_id] = result
                scores.append(result["score"])
            except Exception as e:
                results[task_id] = {
                    "error": str(e),
                    "score": 0.0,
                }
                scores.append(0.0)

        average = sum(scores) / len(scores) if scores else 0.0

        return {
            "task_1_score": results.get("task_1_single_service_crash", {}).get("score", 0.0),
            "task_2_score": results.get("task_2_db_cascade_failure", {}).get("score", 0.0),
            "task_3_score": results.get("task_3_distributed_ghost_incident", {}).get("score", 0.0),
            "average": average,
            "details": results,
        }


def save_baseline_results(results: dict[str, Any], output_dir: str = "baseline/results"):
    """Save baseline results to JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/baseline_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    return filename
