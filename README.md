# Archaion Analyzer

**Archaion Analyzer** is a standalone, AI-powered application designed to help developers and architects evaluate legacy software. It connects to a **CAST Imaging MCP (Model Context Protocol) Server** to pull detailed statistics about applications (like how many lines of code they have, what languages they use, and if they contain sensitive data), and then uses **Artificial Intelligence (LLMs like OpenAI, Google Gemini, or OpenRouter)** to automatically generate modernization plans and cloud strategy recommendations.

---

## 🛑 Important License Notice
Before using this software, please read the [LICENSE.md](LICENSE.md).
- You **must give credit** to the original author if you use or modify this project.
- You **must obtain explicit permission** from the author before distributing this software (commercially or non-commercially) or hosting it publicly.

---

## 🌟 Key Features
- **Standalone Design:** Everything runs on a single server (Port 8000). The visual user interface (frontend) and the data engine (backend) are bundled together.
- **No Coding Required:** You do not need to edit any code or `.env` files to connect your tools. The application has a "Settings" button right on the web page where you can safely paste your CAST MCP connection details and your AI keys.
- **Privacy-First:** Your API keys are saved locally in your own browser. The server does not permanently store them, meaning you can safely deploy this tool for your team to use with their own personal keys.

---

## 🚀 How to Install and Run

There are two main ways to run this application. You can use **Docker** (the easiest and most reliable method), or you can install it directly onto your computer (**Local Setup**).

### Method 1: Running with Docker (Recommended for all platforms)
Docker packages the application so you don't have to worry about installing the right version of Python.

**Requirements:**
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**Steps:**
1. Open your computer's terminal (Command Prompt/PowerShell on Windows, or Terminal on Mac/Linux).
2. Navigate to the Archaion project folder.
3. Run the following command:
   ```bash
   docker-compose up --build
   ```
4. Wait a minute for it to finish setting up.
5. Open your web browser and go to: `http://localhost:8000`

To stop the application, just press `CTRL + C` in the terminal, or run `docker-compose down`.

---

### Method 2: Local Installation (Without Docker)

If you prefer not to use Docker, you can run the application directly using Python.

**Requirements for all systems:**
- You must have **Python 3.11 or 3.12** installed on your computer.

#### 🪟 Instructions for Windows:
1. Open **PowerShell**.
2. Navigate to the Archaion folder:
   ```powershell
   cd C:\path\to\Archaion
   ```
3. Create a virtual environment (this keeps the application files isolated from the rest of your computer):
   ```powershell
   python -m venv venv
   ```
4. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(If you get a red error about "Execution Policies", run this command first: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` and try step 4 again).*
5. Install the required files:
   ```powershell
   pip install -r requirements.txt
   ```
6. Start the application:
   ```powershell
   python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
   ```
7. Open your web browser and go to: `http://localhost:8000`

#### 🍎 Instructions for macOS and Linux:
1. Open the **Terminal**.
2. Navigate to the Archaion folder:
   ```bash
   cd /path/to/Archaion
   ```
3. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
4. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
5. Install the required files:
   ```bash
   pip install -r requirements.txt
   ```
6. Start the application:
   ```bash
   python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
   ```
7. Open your web browser and go to: `http://localhost:8000`

---

## ⚙️ How to Use the Application

Once you have opened `http://localhost:8000` in your web browser:
1. Click the **"⚙ SETTINGS"** button in the top right corner.
2. Enter your **CAST MCP URL** (e.g., `http://your-company.castsoftware.com/mcp`).
3. Enter your **CAST MCP X-API-KEY**.
4. Select your preferred **LLM Provider** from the dropdown menu (e.g., OpenRouter, OpenAI, Google Gemini).
5. Enter your personal **LLM API Key** for the provider you selected.
6. Click **Save Configuration**.

The application will immediately connect to your MCP server and populate the left-hand column with all your available applications! Click on any application to view its technical profile, fill out the modernization scope form, and click "Initialize Agents" to watch the AI write a custom modernization report for you.