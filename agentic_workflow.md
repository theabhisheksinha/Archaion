# Agentic Workflow & CrewAI Integration

Archaion Analyzer is an **Agentic Application** powered by **CrewAI**. This document details how the multi-agent workflow operates, how tasks are dynamically assigned, and exactly how a developer can extend this architecture to introduce new AI Agents and capabilities into the ecosystem.

---

## 🧠 The Agentic Paradigm

Unlike traditional software that follows a rigid, linear script, an **Agentic Workflow** utilizes autonomous AI entities (Agents) equipped with specific roles, goals, and backstories. 

In Archaion, the modernization process is treated like a collaborative team of experts:
1. The **User** (Frontend) sets the mission parameters (Target Framework, Risk Profile).
2. The **Data Source** (CAST MCP) provides the structural facts (Application DNA, Flaws).
3. The **Crew** (CrewAI) orchestrates the experts to interpret the facts and write a modernization strategy based on the parameters.

---

## 🏗 CrewAI Architecture in Archaion

The CrewAI implementation is split across a few files:

- Backend entrypoint + SSE stream: `app/backend/main.py`
- Workflow/state: `app/flows/modernization_flow.py`
- Agent + task assembly: `app/backend/crew.py`
- MCP tool adapter for CrewAI: `app/tools/mcp_tools.py`

Agent/task/tool configuration is YAML-driven:
- Agents: `app/agents/config/agents.yaml`
- Tasks: `app/agents/config/tasks.yaml`
- Tools (grouping reference): `app/agents/config/tools.yaml`

The runtime loader lives in `app/backend/crew.py` and maps YAML keys to the internal agent/task assembly.

### 1. Execution Model (UI → Backend → Flow → Crew)
1. The UI starts a mission by POSTing to `/kickoff` (see `app/frontend/main.js`).
2. The UI opens an SSE connection to `/analyze/stream/{job_id}` to stream status updates.
3. The backend creates a `ModernizationFlow`, sets:
   - `flow.state.selected_app_id`
   - `flow.state.mission_params` (includes MCP credentials + mission selections)
4. The flow runs:
   - `discover_portfolio()` (MCP `applications`)
   - `profile_application()` (MCP `stats`)
   - `execute_mission()`:
     - Deterministic report path when `use_llm=false` (default)
     - Optional CrewAI kickoff when `use_llm=true`
     - Regardless of mode, the backend pre‑fetches deterministic evidence (architecture, data, transactions, risks). This evidence is injected into the agentic synthesis to ensure every recommendation cites CAST IDs.

### 2. Crew Assembly (Agents, Tasks, Process)
The `ModernizationCrew` class in `app/backend/crew.py`:
- Chooses an LLM based on `llm_provider` and `llm_key`.
- Attaches MCP-backed tools to agents via `create_mcp_tool(...)`.
- Loads agent roles/goals/backstories and task templates from YAML.
- Builds a `Crew` with a best-effort hierarchical process when supported.

Important behavior:
- The “manager” model is not hardcoded to a different provider. The manager LLM reuses the selected LLM to avoid provider/model mismatch errors (e.g., OpenRouter 404 for an Anthropic model ID).
- Cost controls:
  - OpenRouter internal models default to `openai/gpt-4o-mini`
  - Agents are configured with iteration caps (`max_iter`) to limit retries
  - The flow limits provider/model fallback attempts

New specialist agents (added):
- `architecture_analyst`: maps layers, transactions, and coupling using `architectural_graph`, `applications_transactions`, `applications_data_graphs`.
- `risk_compliance_expert`: audits ISO‑5055, CVE, and structural flaws; can fetch detailed locations via `quality_insight_violations`.
- `modernization_advisor`: pulls advisors/rules/occurrences to generate actionable remediation steps.

New tasks (added) and expected outputs:
- `architecture_analysis_task` → JSON: app, top_layers, interaction_patterns, architectural_coupling, evidence.
- `risk_compliance_audit_task` → JSON: packages_risk, iso5055_summary, top_violations_with_locations, evidence.
- `advisory_suggestions_task` → JSON: applied_advisors, broken_rules, remediation_steps, evidence.
- `synthesis_report_task` → Markdown report (10 sections) citing evidence IDs, with a top‑10 Risks table.

### 3. MCP Tools Inside CrewAI
`app/tools/mcp_tools.py` wraps CAST MCP tools into a CrewAI tool interface.

Practical notes:
- The MCP tool name must exist on the connected CAST MCP server.
- The MCP payload keys must match what the MCP tool expects (for example, some tools expect `application`, some expect `app_name`, etc.).
- The wrapper auto-injects `application` only for application-scoped tools. Portfolio tools (such as `applications_*`) and inter-application dependency tools must not receive an injected `application` field due to MCP schema validation (`additionalProperties: false`).
 - The wrapper now defines **strict Pydantic schemas** per tool. Example: `quality_insight_violations` requires `id` when `include_locations=true` and supports natures: `cloud-detection-patterns`, `green-detection-patterns`, `cve`, `structural-flaws`, `iso-5055`.
 - This prevents silent agent failures and ensures all agent tool calls are valid against the MCP server.

---

## 🛠 How to Add a New Agent to Archaion

Add a new expert agent by editing YAML config and (optionally) the UI mission inputs.

### Step 1: Add an Agent Definition
In `app/agents/config/agents.yaml`, add a new entry:
- `role`
- `goal`
- `backstory`

Then, in `app/backend/crew.py`, map it to an internal agent factory method if needed (follow the style of existing agent methods). If the agent needs CAST data mid-run, attach tools using `self._get_tool(...)`.

### Step 2: Add a Task Definition
In `app/agents/config/tasks.yaml`, add:
- `description` (can include placeholders like `{objective}`, `{dna_profile}`, etc.)
- `expected_output`
- `agent` (must match your agent key)

Then ensure the task is included in `ModernizationCrew.crew()` (add it to the `tasks` list).

### Step 3: Pass New Inputs (If Needed)
If your task template uses a new placeholder, update the `inputs` dict inside `ModernizationFlow.execute_mission()` to include it.

### Step 4: Prefer Deterministic Evidence Collection
If your task needs CAST facts, prefer collecting them in code (MCP tool calls) and passing condensed evidence into the task context. This reduces token usage and avoids agent retry loops.
In Archaion 2.0, the flow always pre‑collects:
- Top‑10 tables `(table | schema | object_id)`
- Top transactions `(transaction | object_id)`
- Top‑10 risks `(type | name | severity | count | id)` (+ locations when requested)

### Step 4: Wire Output Into the UI (Optional)
The UI currently displays `executive_summary` and `iso_5055_flaws` fields in the report response.
If you want a new section rendered separately, extend the report object assembled in `app/backend/main.py` and update `displayReport(...)` in `app/frontend/main.js`.

---

## 🚀 Advanced Capabilities (Future Expansion)

### 1. Parallel Processing
CrewAI support varies by version. The current code attempts hierarchical execution when available and falls back gracefully when not.

### 2. Custom Tools for Agents
Agents can already call MCP tools during execution via the `MCPToolWrapper`. To add a new tool:
1. Identify the exact CAST MCP tool name and required payload keys.
2. Add `self._get_tool("<tool_name>", "<description>")` to the relevant agent method in `app/backend/crew.py`.
3. Validate by running a mission and confirming the tool calls succeed (or fail with a meaningful MCP error).
