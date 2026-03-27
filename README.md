---
title: SRE Incident Environment
emoji: 🚨
colorFrom: red
colorTo: pink
sdk: docker
pinned: false
license: mit
tags:
  - openenv
  - sre
  - devops
  - incident-response
  - fastapi
---

# SRE Incident Environment

SRE Incident Environment is a FastAPI-based simulation environment for training and evaluating agents on production incident response. It exposes realistic operational signals, accepts structured remediation actions and returns deterministic grades so different agent strategies can be compared reliably.

Live deployment: [Hugging Face Space](https://vindicta07-sre-incident-env.hf.space/)

Source code: [GitHub Repository](https://github.com/vindicta07/sre-incident-env)

## Overview

The project models production outages that an SRE might face in a real system. Each task starts with an incident state containing alerts, metrics, logs, recent deploys and service dependencies. An agent interacts with the environment by choosing actions such as checking logs, rolling back a deploy, killing slow queries or reverting a bad config change.

The repository is useful for:

- evaluating incident-handling agents
- building baselines for structured decision making
- testing reward and grading strategies
- deploying a hosted environment on Hugging Face Spaces

## Tasks

| Task | Difficulty | Description |
| --- | --- | --- |
| Single Service Crash | Easy | A bad deploy takes down one core service and the agent must identify the issue and recover it |
| Database Cascade Failure | Medium | Database pressure causes downstream failures and the agent must identify the trigger and stabilize the system |
| Distributed Ghost Incident | Hard | A misleading multi-service outage requires identifying the real root cause before recovery |

## What The API Exposes

The app serves ReDoc at the root path and provides these main endpoints:

- `POST /reset` to start a new task session
- `POST /step` to apply an action to the current session
- `GET /state` to inspect current state without advancing the episode
- `GET /tasks` to list available tasks and supported action schema
- `POST /grader` to score an episode history
- `POST /baseline` to run the included Hugging Face powered baseline
- `GET /baseline/status` to verify baseline readiness
- `GET /health` for liveness checks

## Project Structure

- `api/` contains the FastAPI app, routes and request or response schemas
- `environment/` contains the simulator, reward logic, models and task scenarios
- `graders/` contains deterministic grading logic for each task
- `baseline/` contains prompting and inference code for the Hugging Face baseline agent
- `tests/` contains API, environment and grader tests
- `Dockerfile` contains the deployment setup used by Hugging Face Spaces
- `openenv.yaml` contains environment metadata

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 7860
```

Then open:

```text
http://localhost:7860/
```

## Example Usage

Start a session:

```bash
curl -X POST "http://localhost:7860/reset" \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"task_1_single_service_crash\"}"
```

Take a step with the returned `session_id`:

```bash
curl -X POST "http://localhost:7860/step" \
  -H "Content-Type: application/json" \
  -d "{\"action_type\":\"check_logs\",\"target_service\":\"auth-service\",\"session_id\":\"YOUR_SESSION_ID\"}"
```

## Hugging Face Spaces Deployment

This repository is configured for Docker Spaces.

1. Create a Space and choose `Docker` as the SDK
2. Push this repository to the Space
3. Add `HF_TOKEN` under `Settings -> Variables and secrets`
4. Wait for the build to complete

After deployment:

- `/` serves ReDoc
- `/health` should return a healthy response
- `/baseline/status` should report whether the baseline is ready

Deployed Space:

- App URL: [https://vindicta07-sre-incident-env.hf.space/](https://vindicta07-sre-incident-env.hf.space/)
- Space page: [https://huggingface.co/spaces/vindicta07/sre-incident-env](https://huggingface.co/spaces/vindicta07/sre-incident-env)

## Baseline Agent

The included baseline uses Hugging Face Inference API and reads the access token from `HF_TOKEN`. The baseline route is optional for the rest of the environment, so the core API will still run without it. If `HF_TOKEN` is missing, only the baseline-related endpoint will fail.

## Testing

Run the test suite with:

```bash
python -m pytest tests -q
```

## License

This project is available under the MIT License. See [LICENSE](/c:/Users/admin/OneDrive/Desktop/Preparation_Pathak/sre-incident-env/LICENSE) for details.
