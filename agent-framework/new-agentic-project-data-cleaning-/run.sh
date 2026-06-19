#!/bin/bash
set -e

# Start ARQ worker in the background
arq finflow_agent.api.WorkerSettings &

# Start FastAPI server
uvicorn finflow_agent.api:app --host 0.0.0.0 --port 8001
