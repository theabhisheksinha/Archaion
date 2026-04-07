# Archaion Architecture

## Overview
- Purpose: Standalone modernization analysis app (UI + API on a single port) that runs locally and can be containerized with Docker.
- Runtime: FastAPI backend serves static frontend assets and orchestrates a multi-step workflow that calls CAST Imaging MCP and (optionally) CrewAI.
- LLM: Selected at runtime (OpenRouter/OpenAI/Gemini/Azure). When CrewAI cannot import/install, the flow can fall back to LiteLLM completions.

## Repository Layout (Current)
- Frontend (static): [index.html](file:///c:/Personal-docs/Archaion/Archaion/app/frontend/index.html), [main.js](file:///c:/Personal-docs/Archaion/Archaion/app/frontend/main.js), [style.css](file:///c:/Personal-docs/Archaion/Archaion/app/frontend/style.css)
- Backend (FastAPI): [main.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/main.py)
- Workflow/state machine: [modernization_flow.py](file:///c:/Personal-docs/Archaion/Archaion/app/flows/modernization_flow.py)
- CrewAI multi-agent assembly: [crew.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/crew.py)
- CrewAI MCP tool adapter: [mcp_tools.py](file:///c:/Personal-docs/Archaion/Archaion/app/tools/mcp_tools.py)
- Agent/task YAML (future-friendly): [agents.yaml](file:///c:/Personal-docs/Archaion/Archaion/app/agents/config/agents.yaml), [tasks.yaml](file:///c:/Personal-docs/Archaion/Archaion/app/agents/config/tasks.yaml)
- Container setup: [Dockerfile](file:///c:/Personal-docs/Archaion/Archaion/Dockerfile), [docker-compose.yml](file:///c:/Personal-docs/Archaion/Archaion/docker-compose.yml)
- Dependency lock (important): [requirements.txt](file:///c:/Personal-docs/Archaion/Archaion/requirements.txt)

## High-Level Data Flow
- Portfolio discovery
  - UI calls `/applications`
  - Backend calls CAST MCP tool `applications`
  - UI renders selectable portfolio
- DNA profiling
  - UI calls `/dna?app_id=...`
  - Backend calls CAST MCP tool `stats` (and may call other tools depending on implementation)
  - UI renders “DNA” view for the selected application
- Mission execution
  - UI posts mission params to `/analyze`
  - Backend builds an inputs payload (DNA, ISO 5055 flaws, user choices)
  - Backend runs CrewAI kickoff (threaded) and streams status updates to the UI
  - Backend returns mission report + validation report and enables DOCX export

## Backend Endpoints (Current)
- GET `/config` → server defaults (e.g., default MCP URL)
- GET `/applications` → portfolio list via MCP
- GET `/dna?app_id=...` → profile via MCP
- POST `/analyze` → orchestrates mission (MCP + CrewAI/LiteLLM)
- GET `/download-docx` → converts generated Markdown to DOCX

## MCP Integration Details
- Transport: HTTP via the MCP Python client session in [main.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/main.py)
- Auth: request header `x-api-key: <CAST_X_API_KEY>`
- Notable tool name mapping:
  - UI refers to `iso-5055-flaws`, backend maps it to MCP tool `iso_5055_flaws`

## LLM Integration Details
- CrewAI path: [crew.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/crew.py) configures the LLM per provider.
- Manager model: Uses the same LLM as the selected provider/model to avoid OpenRouter “missing endpoint” errors for unrelated providers.
- Fallback: [modernization_flow.py](file:///c:/Personal-docs/Archaion/Archaion/app/flows/modernization_flow.py) can call `litellm.acompletion` when CrewAI is unavailable.

## Security Model (Local)
- Keys are entered in the UI and stored in browser localStorage.
- Server does not persist keys; it receives them via request headers/body and uses them for the request lifecycle.
- Backend avoids logging secrets; errors are returned as safe messages.

## Validation & Maintenance
- Fast import/bytecode checks:
  - `python -c "from app.backend.main import app; print('ok')"`
  - `python -m compileall app -q`
- If changing LLM providers/models, validate by running a mission and confirming the “CrewAI Agents started processing” step completes without provider errors.
