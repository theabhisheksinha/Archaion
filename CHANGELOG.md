# Changelog

All notable changes to this project are documented here. This file summarizes functional updates to the UI, backend flow, CrewAI agents, and documentation.

## [2.0.0] - 2026-04-10

### Added
- Evidence-first pipeline even with LLM enabled: backend pre-fetches deterministic CAST evidence and injects it into the agentic synthesis step so recommendations cite CAST Object/Violation IDs.
- Mission Command Center toggles:
  - Enable AI Generative Agents (CrewAI) → `use_llm=true`
  - Include Detailed Locations & Code Snippets (Violations) → `include_locations=true`
- Strict Pydantic schemas for MCP tools in the CrewAI adapter (e.g., `quality_insight_violations` requires `id` when `include_locations=true`; validated `nature` values).
- New specialized agents and tasks:
  - `architecture_analyst` → `architecture_analysis_task`
  - `risk_compliance_expert` → `risk_compliance_audit_task`
  - `modernization_advisor` → `advisory_suggestions_task`
- Robust Markdown renderer in the UI:
  - Proper thead/tbody tables, consistent cell styling, bullet lists, headers, code blocks.
  - Safe fallbacks for missing values in cells (“-”) to avoid empty cells.

### Changed
- Deterministic report generation now composes reader-friendly tables:
  - Data Architecture & Hotspots: top‑10 tables with case-insensitive de‑duplication.
  - Transaction Flows & Coupling: top flows with name inference (`name|displayName|transaction_name|label`) and de‑duplication.
  - Risk & ISO 5055 Findings: top‑10 by count (when available) with columns `type | name | severity | count | id`; optional “Detailed Occurrences (Sample)” when `include_locations=true`.
- Crew assembly updated to include new agents and to pass the pre‑fetched deterministic evidence into the synthesis task.
- UI report rendering upgraded to prevent broken formatting when multiple tables/sections are present.

### Fixed
- Eliminated superficial “Not available from MCP output” and placeholder values by injecting deterministic evidence into the agentic path.
- Prevented silent agent failures on MCP calls by validating arguments with strict schemas.
- Avoided table display anomalies (blank headers, misaligned cells, duplicate rows).

### Documentation
- README.md: Added “What’s New in 2.0”, Deterministic Mode details, robust Report Formatting Guide, and clarified toggles.
- architecture.md: Documented evidence injection, include_locations, tool contracts, and report-quality controls.
- agentic_workflow.md: Described new agents/tasks, enforced tool schemas, and evidence injection into synthesis.
- agents_responsibility_matrix.md: Updated ownership for sections; added new agents and the `quality_insight_violations` contract.

### Notes for Upgraders
- If your MCP server supports code snippets for violations, enable it to enrich “Detailed Occurrences” when `include_locations=true`.
- Agents and tasks are now stricter about table outputs; ensure any custom extensions follow the documented table formats.

---

## [1.x.x] - Previous
- Initial standalone app with deterministic path by default and optional CrewAI integration.
- Basic tables and narrative without strict evidence injection or top‑N shaping.

