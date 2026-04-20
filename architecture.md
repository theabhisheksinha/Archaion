# Archaion Architecture

## Overview
- **Purpose**: Standalone modernization analysis app (UI + API on a single port) that runs locally and can be containerized with Docker.
- **Runtime**: FastAPI backend serves static frontend assets and orchestrates a multi-step workflow that calls CAST Imaging MCP and optionally CrewAI.
- **Determinism**: Default execution path generates a report from CAST MCP tool outputs without calling an LLM (`use_llm=false`).
- **LLM Integration**: Selected at runtime (OpenRouter/OpenAI/Gemini/Azure) and used only when explicitly enabled.
- **Data Persistence**: Uses a Redis intermediate layer (or local in-memory dict fallback) to cache heavy MCP payloads, protecting the LLM context window.

## Repository Layout
- **Frontend (static)**: `app/frontend/index.html`, `main.js`, `style.css`
- **Backend (FastAPI)**: `app/backend/main.py`
- **Data Persistence**: `app/backend/redis_manager.py` (Redis client + `_fallback_store` for local execution)
- **Workflow/state machine**: `app/flows/modernization_flow.py`
- **CrewAI multi-agent assembly**: `app/backend/crew.py`
- **CrewAI MCP tool adapters**: `app/tools/mcp_tools.py`
- **Document Generator**: `app/tools/document_generator.py` (Robust Markdown to MS Word DOCX converter)
- **Agent/task YAML**: `app/agents/config/agents.yaml`, `tasks.yaml`
- **Container setup**: `Dockerfile` (Ubuntu 24.04 multi-stage), `docker-compose.yml`

## High-Level Data Flow
1. **Portfolio Discovery**: UI calls `/applications` -> Backend calls CAST MCP `applications` -> UI renders list.
2. **DNA Profiling**: UI calls `/dna?app_id=...` -> Backend calls CAST MCP `stats` -> UI renders DNA view.
3. **Mission Execution**:
   - UI posts mission params to `/kickoff` and opens SSE `/analyze/stream/{job_id}`.
   - A unique UUID `execution_id` is generated for data isolation.
   - Backend fetches dynamic MCP tool schemas and saves them to Redis.
   - **When `use_llm=true`**: CrewAI agents execute tasks. When they call an MCP tool, the "Smart Interceptor" (`mcp_tools.py`) executes the tool, caches the massive JSON payload in Redis (namespaced by the `execution_id`), and returns a tiny summary to the LLM.
   - The final synthesis agent uses `FetchRedisDataTool` to retrieve the clean, cached data and writes a grounded Markdown report.
4. **Export**: The UI parses the Markdown into HTML. The user can also hit `/report/download/{job_id}`, which triggers `document_generator.py` to build a beautifully formatted native MS Word DOCX file.

## MCP Integration Details
- Transport: HTTP via the MCP Python client session in `main.py`.
- The CrewAI wrapper defines strict Pydantic schemas per tool in `mcp_tools.py` so agents pass valid payloads (preventing `Missing required argument` errors).

## LLM Integration Details
- **CrewAI Path**: `crew.py` configures the LLM per provider. Forces `Process.sequential` to ensure deterministic hierarchical execution.
- **Cost & Context Controls**:
  - Intermediate Redis caching stops the context window from blowing up.
  - Agent iteration caps (`max_iter`) reduce retries.
  - Agents are explicitly prompted to use LLM Fallback Reasoning to deduce architecture based on the "tech stack" if MCP tools return empty data.
- **Report Generation**: Extracts token metrics (`usage.total_tokens`) and appends them to the UI. Searches for CVEs, CWEs, and Cloud Blockers, assigning Priority and Severity.

## Security Model (Local)
- Keys are entered in the UI and stored in browser `localStorage`.
- Server receives them via request headers/body and uses them ephemerally. No keys are written to disk.

## Deployment Architecture (Dockerized)
1. **FastAPI Container**: Serves the frontend (HTML/JS/CSS) and runs the backend API endpoints. Built on Ubuntu 24.04 with `/opt/venv`.
2. **Redis Container**: Provides intermediate data persistence and caching.

*Note for Local Dev*: If running without Docker via `python -m uvicorn`, `redis_manager.py` gracefully catches the missing connection and routes all cache calls to an internal `_fallback_store` dictionary, ensuring a seamless developer experience.
