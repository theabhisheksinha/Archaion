# Archaion Architecture

## Overview
- Purpose: Standalone modernization analysis app (UI + API on a single port) that runs locally and can be containerized with Docker.
- Runtime: FastAPI backend serves static frontend assets and orchestrates a multi-step workflow that calls CAST Imaging MCP and optionally CrewAI.
- Determinism: Default execution path generates a report from CAST MCP tool outputs without calling an LLM (`use_llm=false`).
- LLM: Selected at runtime (OpenRouter/OpenAI/Gemini/Azure) and used only when explicitly enabled.
- Evidence Injection: Even when LLM is enabled, the backend pre‑fetches deterministic evidence from MCP tools and injects it into the agentic synthesis step to guarantee traceability to CAST IDs.

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
  - Backend calls CAST MCP tool `stats` only (no LLM/CrewAI)
  - UI renders “DNA” view for the selected application
- Mission execution
  - UI posts mission params to `/kickoff` and opens SSE `/analyze/stream/{job_id}`
  - Backend builds mission parameters from Mission Command Center inputs:
    - `objective` (free text)
    - `modernization_goal`, `modernization_type`
    - `risk_profile`
    - `criteria[]` (mapped to MCP `quality_insights(nature=...)`)
    - `advisor_id` (optional)
    - `use_llm` (default false) and `include_locations` (default false)
  - Backend runs `ModernizationFlow` steps and streams status updates
  - Backend produces a deterministic report from MCP evidence when `use_llm=false`
  - When `use_llm=true`, CrewAI agents consume the same evidence block to write a narrative that still cites CAST Object/Violation IDs

## Backend Endpoints (Current)
- GET `/config` → server defaults (e.g., default MCP URL)
- GET `/applications` → portfolio list via MCP
- GET `/dna?app_id=...` → profile via MCP
- GET `/advisors?app_id=...` → advisor list via MCP `advisors(application=..., focus="list")`
- POST `/kickoff` → starts mission (returns `job_id`; returns 409 if already running for the same application)
- GET `/analyze/stream/{job_id}` → SSE stream (status + final report)
- GET `/download-docx` → converts generated Markdown to DOCX

## MCP Integration Details
- Transport: HTTP via the MCP Python client session in [main.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/main.py)
- Auth: request header `x-api-key: <CAST_X_API_KEY>`
- Tool naming follows CAST Imaging MCP tool names (examples used by the app):
  - Portfolio: `applications`, `applications_transactions`, `applications_data_graphs`, `applications_dependencies`, `applications_quality_insights`
  - Application: `stats`, `architectural_graph`, `application_database_explorer`, `transactions`, `transaction_details`, `data_graphs`, `data_graph_details`, `quality_insights`, `quality_insight_violations`, `application_iso_5055_explorer`, `advisors`, `advisor_occurrences`
  
Additional contract notes:
- `quality_insight_violations`: 
  - `application` (required), `nature` (required), `id` (required when `include_locations=true`), `include_locations` (bool), `page` (int)
  - When `include_locations=true`, returns file paths/lines and (optionally) snippets if enabled on the MCP server.
- The CrewAI wrapper defines Pydantic schemas per tool in [mcp_tools.py](file:///c:/Personal-docs/Archaion/Archaion/app/tools/mcp_tools.py) so agents pass valid payloads.

## LLM Integration Details
- CrewAI path: [crew.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/crew.py) configures the LLM per provider.
- Manager model: Uses the same LLM as the selected provider/model to avoid OpenRouter “missing endpoint” errors for unrelated providers.
- Cost controls:
  - OpenRouter internal per-agent models default to `openai/gpt-4o-mini`
  - Agent iteration caps (`max_iter`) are set to reduce retries
  - Model fallback attempts are limited
  
Report generation quality controls:
- The backend pre‑computes concise, reader‑friendly tables:
  - Data Architecture: top‑10 tables `(table | schema | object_id)` with case‑insensitive de‑duplication.
  - Transaction Flows: top flows `(transaction | object_id)` with robust name inference and de‑duplication.
  - Risk & ISO 5055: top‑10 `(type | name | severity | count | id)`; optional “Detailed Occurrences (Sample)” with file:line and object names.

## Security Model (Local)
- Keys are entered in the UI and stored in browser localStorage.
- Server does not persist keys; it receives them via request headers/body and uses them for the request lifecycle.
- Backend avoids logging secrets; errors are returned as safe messages.

## Validation & Maintenance
- Fast import/bytecode checks:
  - `python -c "from app.backend.main import app; print('ok')"`
  - `python -m compileall app -q`
- If changing LLM providers/models, validate by running a mission and confirming the “CrewAI Agents started processing” step completes without provider errors.
 - If risk locations are requested, validate calls to `quality_insight_violations` include `id` and `include_locations=true` and that the server’s code snippets feature (if any) is configured.
