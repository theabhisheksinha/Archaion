<div align="center">
  <img src="app/images/Archaion%20-%20bright.png" alt="Archaion Analyzer" width="600">
</div>

# Archaion Analyzer

![Version](https://img.shields.io/badge/version-2.0.0-blue) [![Changelog](https://img.shields.io/badge/CHANGELOG-md-lightgrey)](./CHANGELOG.md) ![Mode](https://img.shields.io/badge/default-Deterministic-success) ![LLM](https://img.shields.io/badge/LLM-Optional-yellow) ![MCP](https://img.shields.io/badge/CAST%20MCP-%E2%89%A5%20v3-8A2BE2) [![License](https://img.shields.io/badge/license-Custom-important)](./LICENSE.md) ![Port](https://img.shields.io/badge/port-9999-informational)

**Archaion Analyzer** is an application modernization analyzer powered by the **CAST Imaging MCP (Model Context Protocol)**. It evaluates legacy software using deterministic facts pulled from CAST Imaging tools (stats, transactions, data graphs, architecture, and quality insights). It can optionally orchestrate **LLMs (OpenAI, Google Gemini, OpenRouter, Azure AI)** via CrewAI, minimizing token usage by utilizing a Redis-backed intermediate data layer to keep outputs grounded in MCP evidence.

## 🔗 Links
- Docker Hub Image: https://hub.docker.com/r/theabhisheksinha/archaion-analyzer
- GitHub Repository: https://github.com/theabhisheksinha/Archaion
- Developer Docs: `playbook.md`, `architecture.md`, `agentic_workflow.md`

---

## 🛑 Important License Notice
Before using this software, please read the [LICENSE.md](LICENSE.md).
- You **must give credit** to the original author if you use or modify this project.
- You **must obtain explicit permission** from the author before distributing this software (commercially or non-commercially) or hosting it publicly.

---

## 🌟 Key Features
- **Standalone Design:** Everything runs on a single server (Port **9999**). Visual UI and backend are bundled together.
- **No Coding Required:** Manage CAST MCP connection details and AI keys securely in the browser via the "Settings" UI.
- **Privacy-First:** API keys are saved locally in your browser's `localStorage` and never permanently stored on the server.
- **Redis Data Isolation:** MCP payloads are huge. Archaion uses Redis (or a local in-memory fallback) to intercept, cache, and clean large MCP JSON responses, feeding only token-efficient summaries to the LLM context window.
- **Docker-Ready:** Ships with a multi-stage Ubuntu 24.04 Dockerfile and a `docker-compose.yml` that wires up the app and Redis seamlessly.
- **Deterministic by Default:** A UI toggle allows generating a report strictly from CAST evidence without invoking the LLM (faster, zero token cost).
- **Beautiful Exports:** View the report in the browser with robust Markdown styling, or click **Download DOCX** for a cleanly formatted Microsoft Word document complete with native tables, headers, and code snippets.
- **Token Metrics:** View exact token consumption (Total, Prompt, Completion) directly in the UI.

---

## 🚀 Getting Started (Execution Guide)

Archaion can be run in two ways: via **Docker (Recommended)** or **Locally (Virtual Environment)**.

### Option 1: Running via Docker (Recommended)
This is the foolproof method. It automatically spins up the Python backend, the frontend, and the Redis server in an isolated environment.

**Prerequisites:**
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**Steps:**
1. Open your terminal and navigate to the project directory.
2. Run the following command:
   ```bash
   docker-compose up --build -d
   ```
3. Open your web browser and navigate to: `http://localhost:9999`
4. To stop the application, run:
   ```bash
   docker-compose down
   ```

### Option 2: Running Locally (Virtual Environment)
If you want to run the application directly on your host machine without Docker (e.g., for development), Archaion features an **In-Memory Fallback**, meaning it will still work perfectly even if you don't have a local Redis server installed!

**Prerequisites:**
- Python 3.10+ installed.

**Steps:**
1. Open your terminal (PowerShell on Windows, or bash on Mac/Linux) in the project directory.
2. Create a Python Virtual Environment:
   ```bash
   python -m venv .venv
   ```
3. **Activate the Virtual Environment (Crucial Step):**
   - On **Windows (PowerShell)**:
     ```powershell
     .\.venv\Scripts\activate
     ```
   - On **Mac/Linux**:
     ```bash
     source .venv/bin/activate
     ```
   *(You should see `(.venv)` appear at the beginning of your terminal prompt).*
4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Start the server:
   ```bash
   python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 9999 --reload
   ```
6. Open your web browser and navigate to: `http://localhost:9999`

---

## ⚙️ How to Use the Application

Once you have opened `http://localhost:9999`:
1. Click the **"⚙" (Gear Icon)** in the top right corner.
2. Enter your **CAST MCP URL** (e.g., `http://your-company.castsoftware.com/mcp`) and **X-API-KEY**.
3. Select your preferred **LLM Provider** (e.g., OpenRouter, OpenAI, Gemini) and enter your **LLM API Key**.
4. Click **Save Configuration**.
5. Select an application from the **Portfolio** list on the left.
6. Review the **Application Technical Profile** (DNA).
7. In the **Mission Command Center**, define your objective, modernization goal, risk profile, and desired toggles:
   - **Enable AI Generative Agents**: Sets `use_llm=true`. (If disabled, generates a deterministic report instantly).
   - **Include Detailed Locations**: Fetches file paths, line numbers, and code snippets for violations.
8. Click **Initialize Agents** to start the mission.

> **Note:** The final report will include neatly formatted tables (Data Hotspots, Transaction Flows, Risk & ISO 5055 with CVE/CWE blockers) and Token Usage metrics. You can export this to MS Word by clicking **Download DOCX**.

---

## 🧾 Report Formatting Guide
Archaion renders Markdown to a reader‑friendly report in the UI and DOCX export. 
- **Section 3: Current‑State Architecture** (Nodes/links and top node groups)
- **Section 4: Data Architecture & Hotspots** (Top‑10 tables with schema and object IDs)
- **Section 5: Transaction Flows & Coupling** (Top flows inferred from `name|displayName|transaction_name`)
- **Section 6: Risk & ISO 5055 Findings** (Top‑10 table sorted by count, explicitly identifying CVEs, CWEs, and Cloud Blockers, including severity/priority mappings)
- **Section 7: Advisory Suggestions** (Rule lists mapped to Advisor IDs)
