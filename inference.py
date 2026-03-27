"""Compatibility entrypoint for platforms that expect inference.py at repo root."""

from __future__ import annotations

import json
import os
from typing import Any

from baseline.inference import BaselineAgent, save_baseline_results


def run_baseline(
    hf_token: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Run the bundled baseline agent across all tasks."""
    agent = BaselineAgent(hf_token=hf_token, model=model)
    return agent.run_all_tasks()


if __name__ == "__main__":
    results = run_baseline(
        hf_token=os.environ.get("HF_TOKEN"),
        model=os.environ.get("HF_MODEL"),
    )
    output_path = save_baseline_results(results)
    print(json.dumps({"results": results, "saved_to": output_path}, indent=2))
