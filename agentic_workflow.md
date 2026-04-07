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

The `app/agents/config/*.yaml` files are present for readability and future refactors, but the current runtime flow builds agents/tasks in Python.

### 1. Execution Model (UI → Backend → Flow → Crew)
1. The UI starts a mission by POSTing to `/kickoff` (see `app/frontend/main.js`).
2. The UI opens an SSE connection to `/analyze/stream/{job_id}` to stream status updates.
3. The backend creates a `ModernizationFlow`, sets:
   - `flow.state.selected_app_id`
   - `flow.state.mission_params` (includes MCP credentials + LLM provider/key)
4. The flow runs:
   - `discover_portfolio()` (MCP `applications`)
   - `profile_application()` (MCP `stats`)
   - `execute_mission()` (CrewAI kickoff in a worker thread)
   - `validate_iso5055()` (final status; validation is produced by the Crew)

### 2. Crew Assembly (Agents, Tasks, Process)
The `ModernizationCrew` class in `app/backend/crew.py`:
- Chooses an LLM based on `llm_provider` and `llm_key`.
- Attaches MCP-backed tools to agents via `create_mcp_tool(...)`.
- Defines agent roles/goals/backstories and task templates (Python dicts).
- Builds a `Crew` with a best-effort hierarchical process when supported.

Important behavior:
- The “manager” model is not hardcoded to a different provider. The manager LLM reuses the selected LLM to avoid provider/model mismatch errors (e.g., OpenRouter 404 for an Anthropic model ID).

### 3. MCP Tools Inside CrewAI
`app/tools/mcp_tools.py` wraps CAST MCP tools into a CrewAI tool interface.

Practical notes:
- The MCP tool name must exist on the connected CAST MCP server.
- The MCP payload keys must match what the MCP tool expects (for example, some tools expect `application`, some expect `app_name`, etc.).

---

## 🛠 How to Add a New Agent to Archaion

Add a new expert agent by editing `app/backend/crew.py` and (optionally) the UI inputs.

### Step 1: Add an Agent Definition
In `ModernizationCrew._AGENTS`, add a new entry:
- `role`
- `goal`
- `backstory`

Then add a method that returns a CrewAI `Agent` (follow the style of existing agent methods).
If the agent needs CAST data mid-run, attach tools using `self._get_tool(...)`.

### Step 2: Add a Task Definition
In `ModernizationCrew._TASKS`, add:
- `description` (can include placeholders like `{objective}`, `{dna_profile}`, etc.)
- `expected_output`
- `agent` (must match your agent key)

Then ensure the task is included in `ModernizationCrew.crew()` (add it to the `tasks` list).

### Step 3: Pass New Inputs (If Needed)
If your task template uses a new placeholder, update the `inputs` dict inside `ModernizationFlow.execute_mission()` to include it.

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
