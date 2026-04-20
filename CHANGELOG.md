# Changelog

All notable changes to this project are documented here. This file summarizes functional updates to the UI, backend flow, CrewAI agents, and documentation.

## [2.1.0] - 2026-04-20

### Added
- **Redis & In-Memory Persistence Layer**: Implemented a caching layer (`app/backend/redis_manager.py`) to intercept massive MCP JSON payloads. This prevents LLM context window blowouts. Includes an in-memory fallback `_fallback_store` so the app runs locally without requiring a Redis server.
- **CVE, CWE, and Cloud Blocker Identification**: Agents now explicitly search for and map CVEs, CWEs, and Cloud Blockers into the Risk & ISO 5055 Findings tables, including Severity, Priority, and Recommendations.
- **Token Consumption Metrics**: The UI now accurately extracts and displays Total, Prompt, and Completion token usage directly at the bottom of the modernization report.
- **LLM Fallback Reasoning**: Agents are now explicitly instructed in their prompts to use foundational technical reasoning (based on the app's tech stack) to deduce architecture if MCP tools return empty data.

### Fixed
- **MS Word DOCX Formatting & Crash Fix**: Completely rewrote `app/tools/document_generator.py`. Fixed a critical bug where MS Word would crash (`Word experienced an error trying to open the file`) due to empty table columns. The DOCX export now beautifully supports native Word tables, headers, lists, code blocks, and bold text.
- **UI Markdown `<strong>` Tag Fix**: Fixed an issue where the LLM generated literal HTML `<strong>` tags, causing them to render as raw text in the UI. The frontend now sanitizes and normalizes these back to Markdown before escaping HTML.
- **Pydantic Validation Errors**: Fixed strict schema mismatches (`Missing required argument` / `Unexpected keyword argument`) in the MCP tool interceptors.
- **Portfolio Data Isolation**: Removed portfolio-level tools from single-application agents to prevent data hallucinations across applications. Data is now isolated per run using a unique `execution_id` UUID.

### Changed
- **Docker Environment**: Upgraded the Dockerfile to use a multi-stage build on `ubuntu:24.04` with a dedicated Python virtual environment (`/opt/venv`).
- **Legacy Parser Removal**: Deleted 300+ lines of legacy hardcoded Python Markdown parsing in `modernization_flow.py` to directly utilize the LLM's superior final generated Markdown report (`raws[-1]`).

---

## [2.0.0] - 2026-04-10
- Evidence-first pipeline even with LLM enabled: backend pre-fetches deterministic CAST evidence.
- Mission Command Center toggles (Enable AI Generative Agents, Include Detailed Locations).
- Strict Pydantic schemas for MCP tools in the CrewAI adapter.
- Robust Markdown renderer in the UI (tables, lists, headers).

---

## [1.x.x] - Previous
- Initial standalone app with deterministic path by default and optional CrewAI integration.
