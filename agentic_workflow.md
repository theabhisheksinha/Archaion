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

The CrewAI implementation lives primarily within the `app/flows/modernization_flow.py` and the `app/agents/config/` YAML files.

### 1. The Configuration Files (The "DNA" of the Agents)
Instead of hardcoding prompts deep inside Python functions, CrewAI promotes separating logic into easily readable YAML files.

- **`app/agents/config/agents.yaml`**: Defines *who* is doing the work.
  - `micro2mono_agent`: An architectural expert specializing in breaking down monoliths.
  - `validator_agent`: A quality gatekeeper strictly adhering to ISO 5055 standards.

- **`app/agents/config/tasks.yaml`**: Defines *what* work needs to be done.
  - `decomposition_task`: Takes the CAST MCP DNA and user parameters to write the initial modernization plan. Assigned to the `micro2mono_agent`.
  - `validation_task`: Reviews the output of the first task against the CAST MCP ISO 5055 flaws to ensure the proposed architecture is safe. Assigned to the `validator_agent`.

### 2. The Python Implementation (The Orchestrator)
The `ModernizationCrew` class in `app/flows/modernization_flow.py` is the orchestrator that brings the YAML configurations to life.

```python
@CrewBase
class ModernizationCrew:
    # 1. Loads the YAML configs
    agents_config = 'agents.yaml'
    tasks_config = 'tasks.yaml'

    # 2. Initializes the LLM dynamically (OpenRouter, OpenAI, etc.)
    def __init__(self, llm_provider, llm_key):
        self.llm = LLM(...)

    # 3. Binds the YAML definitions to Python Agent objects
    @agent
    def micro2mono_agent(self) -> Agent: ...

    # 4. Binds the YAML definitions to Python Task objects
    @task
    def decomposition_task(self) -> Task: ...

    # 5. Assembles the Crew and dictates the process (Sequential)
    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential)
```

### 3. The Execution Context
When the user clicks "Initialize Agents" in the UI, the `ModernizationFlow` class takes over:
1. It queries the CAST MCP Server to grab the real-world facts (`dna_profile`, `iso_5055_flaws`).
2. It bundles these facts alongside the user's UI choices (`goal`, `target_framework`) into a single `inputs` dictionary.
3. It calls `crew_instance.kickoff(inputs=inputs)`. CrewAI automatically injects the `inputs` into the placeholders defined in `tasks.yaml` (e.g., `{dna_profile}`).

---

## 🛠 How to Add a New Agent to Archaion

Adding a new expert to the team (for example, a `Security_Auditor_Agent`) is incredibly straightforward. Follow these three steps:

### Step 1: Define the Agent in YAML
Open `app/agents/config/agents.yaml` and add the new role:

```yaml
security_auditor_agent:
  role: "Cybersecurity Specialist"
  goal: "Review the proposed architecture specifically for data leaks and OWASP Top 10 vulnerabilities."
  backstory: "A paranoid, highly detail-oriented security architect who trusts no code and assumes all APIs are publicly exposed."
```

### Step 2: Define the Task in YAML
Open `app/agents/config/tasks.yaml` and add the task. Assign it to the new agent.

```yaml
security_review_task:
  description: >
    Review the proposed Modernization Plan. Focus specifically on the Data Sensitivity levels provided:
    {data_sensitivity}
    
    Ensure the new architecture includes strict zero-trust networking policies.
  expected_output: >
    A 'Security Audit' section in Markdown.
  agent: security_auditor_agent
```

### Step 3: Bind them in Python
Open `app/flows/modernization_flow.py` and update the `ModernizationCrew` class:

```python
    @agent
    def security_auditor_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['security_auditor_agent'],
            llm=self.llm,
            verbose=True
        )

    @task
    def security_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['security_review_task']
        )
```

### Step 4: (Optional) Update the Inputs
If your new task requires a new piece of data (like `{data_sensitivity}` in the example above), ensure you pass it into the `inputs` dictionary in the `execute_mission` function before calling `kickoff()`:

```python
inputs = {
    "dna_profile": ...,
    "iso_5055_flaws": ...,
    "data_sensitivity": json.dumps(self.state.dna_profile.get("Data_Sensitivity_levels", [])) # New input!
}
```

---

## 🚀 Advanced Capabilities (Future Expansion)

### 1. Parallel Processing
Currently, the Archaion Crew operates sequentially (`Process.sequential`). This means the Validator waits for the Architect to finish before starting. 
If you add multiple independent reviewers (e.g., a Security Agent and a Performance Agent), you can change the process to `Process.hierarchical` or configure asynchronous tasks in CrewAI to speed up execution.

### 2. Custom Tools for Agents
Currently, the FastAPI backend fetches the CAST MCP data *before* the Crew starts. In the future, you can give the agents direct access to the CAST MCP tools!
By defining a custom tool in `app/agents/tools/`, you can empower the agent to query the MCP server autonomously *during* its thought process if it decides it needs more information about a specific code element.