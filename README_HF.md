---
title: SRE Incident Environment
emoji: 🚨
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
---

# SRE Incident Environment

Train AI agents to diagnose and resolve production incidents like an expert SRE.

## Quick Start

```bash
# Reset environment and start episode
curl -X POST https://your-space.hf.space/reset -H "Content-Type: application/json" -d '{"task_id": "task_1_single_service_crash"}'

# Take an action
curl -X POST https://your-space.hf.space/step -H "Content-Type: application/json" -d '{"action_type": "check_logs", "target_service": "auth-service", "session_id": "your-session-id"}'
```

## Available Tasks

1. **Single Service Crash** (Easy) - Rollback a bad deploy
2. **Database Cascade** (Medium) - Kill slow queries and disable feature flag
3. **Distributed Ghost** (Hard) - Fix config + circuit breakers

## API Endpoints

- `POST /reset` - Start new episode
- `POST /step` - Take action
- `GET /state` - Current state
- `GET /tasks` - List tasks
- `POST /grader` - Grade episode
