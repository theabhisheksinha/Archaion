<div align="center">
  <img src="app/images/Archaion%20-%20bright.png" alt="Archaion Analyzer" width="600">
</div>

# Archaion Analyzer

**Archaion Analyzer** is the ** agentic application** powered by the **CAST Imaging MCP (Model Context Protocol)**. It is a standalone, AI-driven platform designed to help developers and architects evaluate legacy software. It connects to the CAST MCP Server to pull detailed architectural statistics (like lines of code, element types, and sensitive data detection), and orchestrates **Artificial Intelligence (LLMs like OpenAI, Google Gemini, or OpenRouter via CrewAI)** to autonomously generate comprehensive modernization plans and cloud strategy recommendations.

## 🔗 Links
- Docker Hub Image: https://hub.docker.com/r/theabhisheksinha/archaion-analyzer
- GitHub Repository: https://github.com/theabhisheksinha/Archaion
- Developer Docs: `playbook.md`, `agentic_workflow.md`

---

## 🛑 Important License Notice
Before using this software, please read the [LICENSE.md](LICENSE.md).
- You **must give credit** to the original author if you use or modify this project.
- You **must obtain explicit permission** from the author before distributing this software (commercially or non-commercially) or hosting it publicly.

---

## 🌟 Key Features
- **Standalone Design:** Everything runs on a single server (Port **9999**). The visual user interface (frontend) and the data engine (backend) are bundled together.
- **No Coding Required:** You do not need to edit any code or `.env` files to connect your tools. The application has a "Settings" button right on the web page where you can safely paste your CAST MCP connection details and your AI keys.
- **Privacy-First:** Your API keys are saved locally in your own browser. The server does not permanently store them, meaning you can safely deploy this tool for your team to use with their own personal keys.
- **Docker-Ready with Log Management:** The Docker setup natively handles log rotation to ensure your host machine never runs out of space.

---

## 🖼 Screenshots

<div align="center">
  <p><strong>Portfolio (Application Selection)</strong></p>
  <img src="app/images/Archaion%20-1.png" alt="Archaion - Portfolio" width="900">
</div>

<div align="center">
  <p><strong>Application Technical Profile (DNA)</strong></p>
  <img src="app/images/Archaion%20-2.png" alt="Archaion - Application Technical Profile" width="900">
</div>

<div align="center">
  <p><strong>Define Your Modernization Scope</strong></p>
  <img src="app/images/Archaion%20-3.png" alt="Archaion - Define Your Modernization Scope" width="900">
</div>

<div align="center">
  <p><strong>Mission Status (Agentic Execution)</strong></p>
  <img src="app/images/Archaion%20-4.png" alt="Archaion - Mission Status" width="900">
</div>

<div align="center">
  <p><strong>Modernization Report</strong></p>
  <img src="app/images/Archaion%20-5.png" alt="Archaion - Modernization Report" width="900">
</div>

<div align="center">
  <p><strong>Modernization Report (Detailed Output)</strong></p>
  <img src="app/images/Archaion%20-6.png" alt="Archaion - Modernization Report Detail" width="900">
</div>

<div align="center">
  <p><strong>Full Page View</strong></p>
  <img src="app/images/Archaion%20-%207.png" alt="Archaion - Full Page View" width="900">
</div>

---

## 🏗 Architecture at a Glance

```mermaid
flowchart LR
    User([User / Architect]) -->|Accesses Port 9999| UI[Frontend UI\nHTML/CSS/JS]
    UI -->|Saves Credentials| Storage[(Browser localStorage)]
    UI -->|API Requests + Headers| Backend[Backend\nFastAPI Server]
    Backend -->|MCP Tool Invocation| MCP[CAST MCP Server]
    Backend -->|Orchestrates| CrewAI[CrewAI Flow Engine]
    CrewAI -->|Agentic Prompts| LLM[LLM Providers\nOpenRouter/OpenAI/Gemini]
```

*(For a deep-dive into the technical architecture and component breakdown, please refer to the `playbook.md` file.)*

---

## 📋 Essential Prerequisites
To use Archaion Analyzer, you must bring your own connection details for two external services. The application acts as a bridge between them but does not provide them for you:

### 1. CAST Software MCP
You must have an active connection to a **CAST Imaging MCP Server**.
- **Version Compatibility:** Archaion requires CAST MCP **v3 or higher**.
- **Credentials:** You will need your organization's specific MCP Server URL and your personal `X-API-KEY` provided by CAST Software.

### 2. Artificial Intelligence (LLM) API Key
Archaion uses generative AI to analyze the architectural statistics and generate the final modernization report. You must provide an API Key from one of the following supported AI providers:
- **OpenAI** (Uses the `gpt-4o` model)
- **Azure AI** (Uses the `azure/gpt-4o` model; requires your Azure endpoint and deployment name configuration)
- **Google Gemini** (Uses the `gemini-1.5-pro` model)
- **OpenRouter** (Uses the `gemini-2.5-flash` model for high-speed routing)

---

## 🚀 How to Install and Run

There are two main ways to run this application: **Local Setup** and **Docker**.

### Method 1: Local Installation (Python Virtual Environment + FastAPI Dev)

**Requirements:**
- Python 3.11 or 3.12 installed on your computer (Windows: use the `py` launcher).
- PowerShell 7+ recommended on Windows.

1. Open your terminal or PowerShell and navigate to the Archaion folder.
2. Create and activate a Python virtual environment. **Use Python 3.11/3.12. Avoid Python 3.14 for this project.**
   ```bash
   # Windows (force Python 3.12 via launcher)
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # macOS/Linux (python3 must point to 3.11 or 3.12)
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
   If you see it trying to install into a global interpreter (example: `Python314\\site-packages`), you are not using the venv interpreter. Use:
   ```bash
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
4. Run the FastAPI development server:
   ```bash
   python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 9999
   # Or (auto-reload for development)
   python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 9999 --reload
   ```
5. Open your web browser and go to: `http://localhost:9999`

---

## 🧩 Developer Notes (Build + Maintenance)

### Python Dependencies That Matter
- `crewai` currently imports `pkg_resources`, which is provided by `setuptools`.
- This repository pins `setuptools==80.10.2` in [requirements.txt](requirements.txt) to keep `pkg_resources` available and avoid startup/import failures.

### Logs (Local + Docker)
- Local runs write logs to `logs/archaion.log` (directory is created automatically next to `app/`).
- Configure via environment variables:
  - `LOG_LEVEL` (default: `INFO`)
  - `LOG_FILE` (default: `logs/archaion.log`; set to `none` to disable file logging)
- Docker logs are handled by Docker’s log driver and rotated (see `docker-compose.yml`).

### OpenRouter Model Selection
- Default OpenRouter model is controlled by:
  - `OPENROUTER_MODEL` (default: `openai/gpt-4o`)
- Per-agent models are selected internally when `OpenRouter` is the chosen provider.
- If OpenRouter returns a 404 model/route error, the backend automatically falls back to a safe default model for all agents.

### Known Runtime Errors & Fixes
- **`ModuleNotFoundError: No module named 'pkg_resources'`**
  - Install dependencies inside the venv and ensure `setuptools==80.10.2` is installed.
- **`ImportError: cannot import name 'BaseTool' from crewai.tools`**
  - Fixed in the codebase by importing `BaseTool` from the compatible CrewAI module path.
- **OpenRouter 404: `No endpoints found for anthropic/claude-...`**
  - Fixed in the codebase by not hardcoding an Anthropic manager model on OpenRouter. The manager LLM reuses the selected provider/model.
- **Uvicorn starts slowly (tens of seconds)**
  - Importing CrewAI + dependencies can be heavy on first run. Wait for “Uvicorn running on …” before testing endpoints.

### Quick Sanity Checks
```bash
.\.venv\Scripts\python.exe -c "from app.backend.main import app; print('ok')"
.\.venv\Scripts\python.exe -m compileall app -q
```

---

### Method 2: Running with Docker (Multi-stage Dockerfile & docker-compose)

This method packages both the UI and the Agentic Backend concurrently.

**Requirements:**
- Docker and docker-compose installed.

1. Open your terminal in the Archaion project folder.
2. Run the following command to build and start the containers:
   ```bash
   docker-compose up --build -d
   ```
3. Wait a few moments for the services to initialize.
4. Open your web browser and go to: `http://localhost:9999`
5. To stop the application, run:
   ```bash
   docker-compose down
   ```

---

## ⚙️ How to Use the Application

Once you have opened `http://localhost:9999` in your web browser:
1. Click the **"⚙" (Gear Icon)** button in the top right corner.
2. Enter your **CAST MCP URL** (e.g., `http://your-company.castsoftware.com/mcp`).
3. Enter your **CAST MCP X-API-KEY**.
4. Select your preferred **LLM Provider** from the dropdown menu (e.g., OpenRouter, OpenAI, Google Gemini).
5. Enter your personal **LLM API Key** for the provider you selected.
6. Click **Save Configuration**.

The application will immediately connect to your MCP server and populate the left-hand column with all your available applications! Click on any application to view its technical profile, fill out the modernization scope form, and click "Initialize Agents" to watch the AI write a custom modernization report for you.
