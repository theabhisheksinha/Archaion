# Archaion Architecture

## Overview
- Purpose: Modernization analysis MVP that runs locally on Windows 11 and can be deployed to AWS Amplify Gen 2 with no architectural changes.
- Core: Frontend (HTML + Tailwind CDN + Vanilla JS) and Backend (FastAPI) orchestrating CrewAI-style agents and integrating CAST Imaging MCP via HTTP.
- LLM: litellm with Gemini 1.5 Pro as primary and OpenRouter fallback.

## Components
- Frontend UI: [index.html](file:///c:/Personal-docs/Archaion/Archaion/src/index.html), [main.js](file:///c:/Personal-docs/Archaion/Archaion/src/main.js)
  - Renders portfolio, DNA badge, Cloud/Strategy selection, Analyze flow, and Markdown report with download.
- Backend API: [handler.py](file:///c:/Personal-docs/Archaion/Archaion/amplify/functions/modernization-handler/handler.py)
  - FastAPI app exposing /health, /applications, /dna, /analyze.
  - MCP client calls CAST Imaging MCP tools with X-API-KEY header.
  - Lifespan management for clean httpx client setup/teardown.
- Amplify Function Definition: [resource.ts](file:///c:/Personal-docs/Archaion/Archaion/amplify/functions/modernization-handler/resource.ts)
  - Exports a Gen 2 function (Python 3.11 runtime) pointing to handler.handler.
  - Local bundling installs Python dependencies and copies sources for deployment packaging.
- Orchestration (Agents): [crew.py](file:///c:/Personal-docs/Archaion/Archaion/amplify/functions/modernization-handler/crew.py)
  - Discovery Specialist, Architecture Analyst, Cloud Architect, conditional Mainframe Specialist.
  - Produces consolidated Markdown report from MCP data + LLM outputs.
- LLM Wrapper: [llm.py](file:///c:/Personal-docs/Archaion/Archaion/amplify/functions/modernization-handler/llm.py)
  - Async generate with Gemini first, falls back to OpenRouter if unavailable or error.
- Windows Tools & Local Runner: [setup_windows.ps1](file:///c:/Personal-docs/Archaion/Archaion/setup_windows.ps1), [run_local.py](file:///c:/Personal-docs/Archaion/Archaion/run_local.py)
  - Creates/activates venv, installs dependencies; launches FastAPI locally with permissive CORS.
- Tests: [test_suite.py](file:///c:/Personal-docs/Archaion/Archaion/test_suite.py)
  - Deterministic validation paths for WebGoat_v3 (Java) and HRMGMT_COB (Mainframe) using mocked MCP/LLM.
- Configuration: [.env.template](file:///c:/Personal-docs/Archaion/Archaion/.env.template)
  - CAST_MCP_URL, CAST_X_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY (no secrets committed).

## Data Flow
- Portfolio View
  - UI loads → calls /applications → backend invokes MCP tool “list_applications” → returns list of apps → user selects via radio.
- DNA Prefetch
  - Selection → UI calls /dna?app_id=… → backend invokes MCP “statistics” → returns tech stack and LoC → UI renders DNA Badge.
- Modernization Analyze
  - UI posts {app_id, cloud_strategy} to /analyze → backend:
    - statistics → get DNA + mainframe flag
    - architectural_graph → topology
    - transaction_summary → transaction overview
    - advisors → maps structural facts to cloud services
    - crew agents use llm.generate to produce narrative → returns consolidated JSON + Markdown.

## Backend Endpoints
- GET /health → status ok
- GET /applications → MCP list_applications
- GET /dna?app_id=… → MCP statistics
- POST /analyze { app_id, cloud_strategy } → orchestration + markdown

## MCP Integration
- HTTP calls to CAST_MCP_URL with header “X-API-KEY: CAST_X_API_KEY”.
- Tools used: list_applications, statistics, architectural_graph, transaction_summary, advisors.
- Implementation avoids logging secrets and handles HTTP/network errors.

## LLM Strategy
- litellm acompletion:
  - Primary: Gemini 1.5 Pro (model: gemini/gemini-1.5-pro).
  - Fallback: OpenRouter (model: openrouter/google/gemini-1.5-pro or compatible).
- Secrets loaded via environment; never logged.

## CORS & Security
- Backend adds permissive CORS during local development to allow UI from file:// or localhost origins.
- No secrets committed; .env used to supply runtime values.
- HTTP errors surfaced without sensitive data.

## Deployment Topology
- Local
  - run_local.py imports FastAPI app from handler.py; venv holds dependencies; UI consumes local endpoints.
- AWS Amplify Gen 2
  - resource.ts defines Python Lambda entry (handler.handler) and bundling for dependencies.
  - Amplify project wires the function into the backend definition; environment variables set at Amplify environment level (CAST_MCP_URL, CAST_X_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY).

## Testing & Validation
- test_suite.py validates:
  - Portfolio shape ({id,name})
  - DNA (“Java” for WebGoat_v3; “COBOL/JCL” for HRMGMT_COB)
  - Analyze: presence/absence of “Mainframe Modernization” depending on DNA
- Health endpoint: GET /health returns {"status":"ok"}.

## Error Handling
- MCP client wraps httpx errors:
  - HTTPStatusError → upstream status
  - RequestError → 502
- /analyze orchestrator continues unless a required MCP call fails; failures return safe messages.

## Extensibility
- Add more agents for quality, security, or cost analysis.
- Enrich MCP adapters for additional tools/endpoints.
- Introduce tracing/metrics (e.g., OpenTelemetry) in handler.py if needed.
