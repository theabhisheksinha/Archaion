# Agents Responsibility Matrix (Roles → Tasks → MCP Tools)

This document maps Archaion’s CrewAI agents to:
- their roles/goals/backstories (as implemented),
- the 10 mandatory report sections,
- and the MCP tools each agent is expected to use, including the typical input keys.

Source of truth: [crew.py](file:///c:/Personal-docs/Archaion/Archaion/app/backend/crew.py) and [mcp_tools.py](file:///c:/Personal-docs/Archaion/Archaion/app/tools/mcp_tools.py).

## Agents (Runtime Definitions)

### Portfolio Specialist (`portfolio_specialist`)
- Role: Discovery Analyst
- Goal: Populate the UI with available applications upon initial load.
- Backstory: Senior IT Asset Manager. You ensure the interface represents the ground truth of the scanned portfolio.
- MCP tools:
  - `applications` (no required inputs)

### System Profile Analyst (`system_profile_analyst`)
- Role: Technical Profiler
- Goal: Generate the System Technical Profile for the selected application.
- Backstory: Architectural Archaeologist. You extract facts (LOC, interactions, stack) to ground the crew's reasoning.
- MCP tools:
  - `stats` (expects `application`)
  - `architectural_graph` (expects `application`)

### Transformation Manager (`transformation_manager`)
- Role: Orchestrator Agent
- Goal: Synthesize user inputs and delegate to specialists; ensure the final report is actionable.
- Backstory: Modernization Program Director. You coordinate the Mission and ensure the final Word report is actionable.
- MCP tools:
  - `advisors` (expects `application`)
  - `architectural_graph_focus` (expects `application`, plus focus/scoping fields depending on server)

### Data Architect (`data_architect`)
- Role: DB Specialist
- Goal: Design the DB migration plan and map CRUD interaction hotspots.
- Backstory: Data Sovereignty Lead. You use deterministic schema maps to propose per-service database splits.
- MCP tools:
  - `application_database_explorer` (expects `application`)
  - `data_graphs` (expects `application`)
  - `data_graphs_involving_object` (expects `application`, plus object identifier fields depending on server)

### Logic Specialist (`logic_specialist`)
- Role: Legacy Transformation specialist
- Goal: Trace functional clusters and mainframe logic paths (when applicable).
- Backstory: Senior Modernization Engineer. You trace JCL/COBOL paths back to cloud-native triggers.
- MCP tools:
  - `transactions` (expects `application`; optional filter fields may include `type`, `name`)
  - `transaction_details` (expects `application` plus a transaction id/key depending on server)
  - `transactions_using_object` (expects `application` plus object id/key depending on server)

### Risk Auditor (`risk_auditor`)
- Role: Quality Specialist
- Goal: Audit the proposed architecture for ISO 5055 compliance (Security/Reliability).
- Backstory: Software Integrity Auditor. You ensure the new microservices are born clean and free of legacy vulnerabilities.
- MCP tools:
  - `application_iso_5055_explorer` (expects `application`)
  - `quality_insights` (expects `application`)
  - `quality_insight_violations` (expects `application`, plus an insight type/key depending on server)

## 10 Mandatory Report Sections (Ownership)

| # | Mandatory Section | Primary Owner | Supporting Agents | Evidence / MCP Tools (typical) |
|---:|---|---|---|---|
| 1 | As‑IS Architecture (Layering/Component structure) | System Profile Analyst | Transformation Manager | `architectural_graph`, `architectural_graph_focus`, `stats` |
| 2 | Present Database Architecture | Data Architect | System Profile Analyst | `application_database_explorer`, `data_graphs` |
| 3 | Database Access Patterns (CRUD hotspots) | Data Architect | Logic Specialist | `data_graphs_involving_object`, `transactions` |
| 4 | API Inventory & Anomalies | Logic Specialist | System Profile Analyst | `transactions`, `transaction_details`, `transactions_using_object` |
| 5 | Proposed Recommended Architecture (Microservices/Containerization) | Transformation Manager | Data Architect, Logic Specialist, Risk Auditor | `advisors` + evidence from 1–4 |
| 6 | Rationale (Why this recommendation?) | Transformation Manager | Risk Auditor | `advisors`, `quality_insights`, `application_iso_5055_explorer` |
| 7 | Mono2micro Decomposition (Code & DB refactoring steps) | Logic Specialist | Data Architect, Transformation Manager | `transactions*`, `data_graphs*` |
| 8 | Cloud Service Map (Target Cloud rationale) | Transformation Manager | Risk Auditor | `advisors` + compliance constraints |
| 9 | Strategic Consulting Conclusion (Risk/ROI) | Risk Auditor | Transformation Manager | `quality_insights`, `quality_insight_violations`, ISO 5055 evidence |
| 10 | Disclaimer | Transformation Manager | (none) | Static text appended in backend/UI/DOCX pipeline |

## Tool Input Keys (Practical Guide)

Archaion injects `application=<selected_app>` automatically for most MCP tools during Crew execution, so agents do not need to remember it.

- Auto-injection behavior: [mcp_tools.py](file:///c:/Personal-docs/Archaion/Archaion/app/tools/mcp_tools.py)
  - Adds `application` if missing for any tool except `applications`.

When adding or debugging tools, verify the MCP server’s required payload keys:
- Some CAST MCP servers may require `app_name` instead of `application`.
- Some tools require additional keys beyond `application` (for example, transaction id, object id, insight type).

## Hierarchy & Execution Shape

The crew is built with a best-effort hierarchical execution mode when supported by the installed CrewAI version.

- Transformation Manager acts as the coordinator (allow_delegation=true).
- Specialists gather evidence via MCP tools and draft their sections.
- Transformation Manager synthesizes the final structured report.

```mermaid
flowchart TB
  UI[Frontend UI] -->|/kickoff + SSE stream| FLOW[ModernizationFlow]
  FLOW --> MCP[CAST Imaging MCP Server]
  FLOW --> CREW[CrewAI Crew (Hierarchical)]

  CREW --> TM[Transformation Manager (Orchestrator)]
  TM --> SPA[System Profile Analyst]
  TM --> DA[Data Architect]
  TM --> LS[Logic Specialist]
  TM --> RA[Risk Auditor]

  SPA -->|stats + architectural_graph| MCP
  TM -->|advisors + architectural_graph_focus| MCP
  DA -->|db + data graphs| MCP
  LS -->|transactions| MCP
  RA -->|quality + ISO 5055| MCP

  CREW --> REPORT[Consolidated Markdown Report + DOCX Export]
  REPORT --> UI
```
