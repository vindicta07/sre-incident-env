---
title: SRE Incident Environment
emoji: ??
colorFrom: red
colorTo: orange
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

SRE Incident Environment is a FastAPI app for training and evaluating agents on production incident response.

## Features

- Three tasks with easy medium and hard difficulty
- Structured observations with alerts metrics logs and service graph data
- Deterministic grading and reward shaping
- Baseline agent that uses Hugging Face Inference API

## Run Locally

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 7860
```

Open `http://localhost:7860/` for ReDoc.

## Hugging Face Spaces Setup

This repository is configured for Docker Spaces.

1. Create a Hugging Face Space with SDK set to `Docker`
2. Push this repository to the Space
3. Add secret in `Settings -> Variables and secrets`
   - `HF_TOKEN`: your Hugging Face access token
4. Wait for the build to finish

## API Endpoints

- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /tasks`
- `POST /grader`
- `POST /baseline`
- `GET /baseline/status`
- `GET /health`

## Notes

- `/baseline` requires `HF_TOKEN`
- `/` serves ReDoc
