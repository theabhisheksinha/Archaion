# Archaion Developer Playbook

Welcome to the internal developer guide for the Archaion Analyzer. This document covers how the architecture works, how to troubleshoot issues, and how to understand the data flow. 

*(If you are just looking for instructions on how to install and run the app, please read the `README.md` file instead).*

---

## 🏛 Architecture Overview

Archaion is a **Stateless, Standalone Monolith** running entirely on Python.

- **Frontend (`app/frontend/`)**: Raw HTML, CSS (Glassmorphism design), and Vanilla JavaScript. It uses `localStorage` to securely save the user's API keys and Server URLs.
- **Backend (`app/backend/`)**: A FastAPI server that handles HTTP requests and serves the static frontend files from the root `/` path. It listens on port `8000`.
- **Flow Engine (`app/flows/`)**: Uses `litellm` to route the AI prompts. It is completely dynamic, supporting OpenAI, Azure, Google Gemini, and OpenRouter based on the user's frontend input.
- **Integration (MCP)**: The backend acts as an HTTP client connecting to a remote CAST Imaging Model Context Protocol (MCP) server.

### Data Flow Example
1. The user opens `http://localhost:8000`.
2. The browser loads `index.html` and `main.js`.
3. The JavaScript fetches the user's stored keys from `localStorage`.
4. `main.js` sends an HTTP GET request to the backend (`/applications`), passing the user's CAST MCP URL and API key inside the HTTP headers (`x-mcp-url` and `x-api-key`).
5. The Python FastAPI backend receives the request, reads the headers, and securely forwards the request to the CAST MCP Server.
6. The CAST MCP Server returns a deeply nested JSON string.
7. The Python backend safely sanitizes the string and passes it back to the frontend.
8. The frontend parses the JSON and populates the user interface dynamically.

---

## 🛠 Troubleshooting Common Issues

### 1. "Failed to fetch" or Blank Screen
- **Issue**: The frontend cannot reach the backend.
- **Solution**: Ensure you are running the application using `uvicorn app.backend.main:app --host 0.0.0.0 --port 8000` (or using Docker). Archaion no longer uses a separate frontend port (`5173`). Everything runs on `8000`.

### 2. "Port 8000 already in use"
- **Issue**: Another application (or an old crashed Archaion server) is still running in the background.
- **Solution (Windows)**:
  1. Open PowerShell.
  2. Find the hidden process: `netstat -ano | findstr :8000`
  3. Look at the last number on the line (the PID).
  4. Kill it: `taskkill /F /PID <PID_NUMBER>`
- **Solution (Mac/Linux)**:
  1. Find the process: `lsof -i :8000`
  2. Kill it: `kill -9 <PID_NUMBER>`

### 3. "No module named 'fastapi'"
- **Issue**: You are not running the application inside the virtual environment where the dependencies were installed.
- **Solution**: Make sure you have activated your virtual environment (`.\venv\Scripts\Activate.ps1` on Windows or `source venv/bin/activate` on Mac/Linux) before running the python command.

### 4. Application List is Empty but No Errors Show
- **Issue**: The CAST MCP credentials entered in the Settings UI are incorrect.
- **Solution**: Click the "⚙ SETTINGS" button in the UI. Ensure the URL is correct (e.g., `https://presales-in.castsoftware.com/mcp`) and that there are no trailing slashes or hidden spaces in your API Key.

### 5. LLM Call Fails during "Initialize Agents"
- **Issue**: The selected LLM Provider and API key combination is invalid.
- **Solution**: Open the Settings UI. If you chose "OpenAI", ensure you pasted an OpenAI key (starting with `sk-...`). If you chose "Google Gemini", ensure it is a valid Gemini key. 

---

## Using Environment Variables (Optional)

Archaion defaults to taking credentials securely from the UI. However, if you prefer using environment variables:
1. Copy `.env.example` to `.env`.
2. Fill in your default keys (e.g., `CAST_X_API_KEY`, `OPENROUTER_API_KEY`).
3. Start the application locally or via `docker-compose up`. The app will automatically fall back to these `.env` values if the user leaves the UI Settings blank.

---

## 📦 File Structure

```text
Archaion/
├── app/
│   ├── agents/          # YAML definitions for AI agent roles
│   ├── backend/         # FastAPI server logic (main.py)
│   ├── flows/           # CrewAI/LiteLLM execution states
│   ├── frontend/        # HTML, CSS, JS static files
│   ├── tasks/           # YAML definitions for AI tasks
│   └── tools/           # Custom Python utilities (like the DOCX generator)
├── docker-compose.yml   # Docker Compose orchestration
├── Dockerfile           # Docker container build instructions
├── LICENSE.md           # Legal usage requirements
├── README.md            # User-facing installation guide
└── requirements.txt     # Python package dependencies
```
