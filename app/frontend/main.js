const API_BASE = ""; // Relative paths so it dynamically uses localhost or Docker IP

let selectedAppId = null;

function getSettings() {
    return {
        mcp_url: localStorage.getItem('cfg_mcp_url') || "",
        mcp_key: localStorage.getItem('cfg_mcp_key') || "",
        llm_provider: localStorage.getItem('cfg_llm_provider') || "openrouter",
        llm_key: localStorage.getItem('cfg_llm_key') || ""
    };
}

function getAuthHeaders() {
    const s = getSettings();
    const headers = {};
    if (s.mcp_url) headers['x-mcp-url'] = s.mcp_url;
    if (s.mcp_key) headers['x-api-key'] = s.mcp_key;
    return headers;
}

async function updateMCPLabel() {
    let mcpUrl = localStorage.getItem('cfg_mcp_url');
    if (!mcpUrl) {
        try {
            const res = await fetch(`${API_BASE}/config`);
            if (res.ok) {
                const data = await res.json();
                mcpUrl = data.default_mcp_url;
            }
        } catch(e) {}
    }
    document.getElementById("mcp-label").textContent = `Connected CAST MCP: ${mcpUrl || 'Unknown'}`;
}

// --- Background Particle Animation ---
function initBackgroundSparks() {
    const canvas = document.getElementById("bg-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    let width = 0;
    let height = 0;
    let dpr = 1;

    const nodeColors = ["#7c8cd4", "#a5b4fc", "#818cf8"];
    const sparkColors = ["#ffffff", "#a5b4fc", "#7c8cd4"];

    let nodes = [];
    let sparks = [];

    function resize() {
        dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
        width = Math.floor(window.innerWidth);
        height = Math.floor(window.innerHeight);
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        initNodes();
    }

    window.addEventListener("resize", resize);

    class Node {
        constructor() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.r = Math.random() * 1.6 + 0.6;
            this.vx = (Math.random() - 0.5) * 0.35;
            this.vy = (Math.random() - 0.5) * 0.35;
            this.c = nodeColors[(Math.random() * nodeColors.length) | 0];
            this.p = Math.random() * Math.PI * 2;
        }

        step() {
            this.p += 0.02;
            this.x += this.vx;
            this.y += this.vy;

            if (this.x < -20) this.x = width + 20;
            if (this.x > width + 20) this.x = -20;
            if (this.y < -20) this.y = height + 20;
            if (this.y > height + 20) this.y = -20;
        }
    }

    class Spark {
        constructor(x, y) {
            const a = Math.random() * Math.PI * 2;
            const s = 1.6 + Math.random() * 2.2;
            this.x = x;
            this.y = y;
            this.vx = Math.cos(a) * s;
            this.vy = Math.sin(a) * s;
            this.life = 24 + ((Math.random() * 28) | 0);
            this.maxLife = this.life;
            this.size = 0.8 + Math.random() * 1.3;
            this.c = sparkColors[(Math.random() * sparkColors.length) | 0];
        }

        step() {
            this.x += this.vx;
            this.y += this.vy;
            this.vx *= 0.985;
            this.vy *= 0.985;
            this.life -= 1;
        }
    }

    function initNodes() {
        const target = Math.max(60, Math.min(160, Math.floor((width * height) / 14000)));
        nodes = [];
        for (let i = 0; i < target; i++) nodes.push(new Node());
        sparks = [];
    }

    function spawnSpark() {
        const n = nodes[(Math.random() * nodes.length) | 0];
        sparks.push(new Spark(n.x, n.y));
    }

    function drawNode(n) {
        const pulse = 0.45 + 0.35 * Math.sin(n.p);
        ctx.globalAlpha = 0.35 + pulse * 0.35;
        ctx.fillStyle = n.c;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();

        ctx.globalAlpha = 0.08 + pulse * 0.06;
        ctx.fillStyle = n.c;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r * 6, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawSpark(s) {
        const t = Math.max(0, s.life / s.maxLife);
        ctx.globalAlpha = 0.65 * t;
        ctx.strokeStyle = s.c;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - s.vx * 2.5, s.y - s.vy * 2.5);
        ctx.stroke();

        ctx.globalAlpha = 0.8 * t;
        ctx.fillStyle = s.c;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();
    }

    function animate() {
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = "rgba(10, 12, 26, 0.22)";
        ctx.fillRect(0, 0, width, height);

        for (const n of nodes) n.step();

        const maxDist = 140;
        const maxDist2 = maxDist * maxDist;

        for (let i = 0; i < nodes.length; i++) {
            const a = nodes[i];
            for (let j = i + 1; j < nodes.length; j++) {
                const b = nodes[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const d2 = dx * dx + dy * dy;
                if (d2 < maxDist2) {
                    const d = Math.sqrt(d2);
                    const alpha = (1 - d / maxDist) * 0.22;
                    ctx.globalAlpha = alpha;
                    ctx.lineWidth = 0.7;
                    ctx.strokeStyle = a.c;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }

        for (const n of nodes) drawNode(n);

        if (sparks.length < 48 && Math.random() < 0.18) spawnSpark();
        const nextSparks = [];
        for (const s of sparks) {
            s.step();
            if (s.life > 0) {
                drawSpark(s);
                nextSparks.push(s);
            }
        }
        sparks = nextSparks;

        requestAnimationFrame(animate);
    }

    resize();
    ctx.fillStyle = "rgba(10, 12, 26, 1)";
    ctx.fillRect(0, 0, width, height);
    requestAnimationFrame(animate);
}
// -----------------------------------

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    initBackgroundSparks();
    updateMCPLabel();
    
    // Settings Modal Logic
    const modal = document.getElementById("settings-modal");
    document.getElementById("settings-btn").onclick = () => {
        const s = getSettings();
        document.getElementById("cfg_mcp_url").value = s.mcp_url;
        document.getElementById("cfg_mcp_key").value = s.mcp_key;
        document.getElementById("cfg_llm_provider").value = s.llm_provider;
        document.getElementById("cfg_llm_key").value = s.llm_key;
        modal.classList.remove("hidden");
    };
    document.getElementById("close-settings").onclick = () => modal.classList.add("hidden");
    
    document.getElementById("save-settings-btn").onclick = () => {
        localStorage.setItem('cfg_mcp_url', document.getElementById("cfg_mcp_url").value.trim());
        localStorage.setItem('cfg_mcp_key', document.getElementById("cfg_mcp_key").value.trim());
        localStorage.setItem('cfg_llm_provider', document.getElementById("cfg_llm_provider").value);
        localStorage.setItem('cfg_llm_key', document.getElementById("cfg_llm_key").value.trim());
        modal.classList.add("hidden");
        updateMCPLabel();
        loadApplications();
    };

    await loadApplications();
});

async function loadApplications() {
    try {
        document.getElementById("status-text").textContent = `Loading applications...`;
        const res = await fetch(`${API_BASE}/applications`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Failed to fetch applications");
        let apps = await res.json();
        
        // Handle the new nested meta/content/isError payload structure
        if (apps && apps.content && Array.isArray(apps.content) && apps.content.length > 0) {
            let innerContent = apps.content[0];
            if (innerContent.type === 'text' && innerContent.text) {
                try {
                    let parsedText = JSON.parse(innerContent.text);
                    if (parsedText.content) {
                        apps = JSON.parse(parsedText.content.replace(/\\n/g, '\n'));
                    }
                } catch(e) {
                    console.error("Failed parsing inner text:", e);
                }
            }
        } else if (apps && apps.structuredContent && apps.structuredContent.content) {
            try {
                apps = JSON.parse(apps.structuredContent.content);
            } catch(e) {}
        }
        
        if (!Array.isArray(apps)) apps = [];

        document.getElementById("status-text").textContent = `Loaded ${apps.length} applications`;
        
        const listContainer = document.getElementById("app-list");
        listContainer.innerHTML = '';
        
        if (apps.length === 0) {
            listContainer.innerHTML = '<p style="padding: 1rem; color: #a39eb8;">No applications found.</p>';
            return;
        }

        apps.forEach(app => {
            const name = typeof app === 'string' ? app : (app.name || app.id || "Unknown App");
            const id = typeof app === 'string' ? app : (app.id || name);
            
            const label = document.createElement("label");
            label.className = "app-item";
            label.innerHTML = `
                <input type="radio" name="app_selection" value="${id}">
                <span style="font-weight:bold;">${name}</span>
            `;
            
            label.querySelector("input").addEventListener("change", (e) => {
                if (e.target.checked) {
                    selectedAppId = e.target.value;
                    loadDNA(selectedAppId);
                    document.getElementById("mission-scoping").classList.remove("hidden");
                }
            });
            
            listContainer.appendChild(label);
        });
        
    } catch (err) {
        document.getElementById("status-text").textContent = `Error: ${err.message}`;
        document.getElementById("app-list").innerHTML = '<p style="padding: 1rem; color: #ff6b6b;">Failed to connect to MCP via backend. Please check Settings.</p>';
    }
}

async function loadDNA(appId) {
    const detailsBox = document.getElementById("dna-details");
    detailsBox.innerHTML = '<p style="color: #a39eb8;">Loading DNA profile...</p>';
    document.getElementById("mf-badge").innerHTML = '<span class="dot" style="background:#f59e0b;"></span> Fetching...';
    
    try {
        const res = await fetch(`${API_BASE}/dna?app_id=${encodeURIComponent(appId)}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Failed to fetch DNA");
        let dna = await res.json();
        
        if (dna && dna.content && Array.isArray(dna.content) && dna.content.length > 0) {
            let innerContent = dna.content[0];
            if (innerContent.type === 'text' && innerContent.text) {
                try {
                    let parsedText = JSON.parse(innerContent.text);
                    if (parsedText.content) {
                        let parsedArray = JSON.parse(parsedText.content.replace(/\\n/g, '\n'));
                        if (Array.isArray(parsedArray) && parsedArray.length > 0) dna = parsedArray[0];
                    }
                } catch(e) {
                    console.error("Failed parsing inner text:", e);
                }
            }
        } else if (dna && dna.structuredContent && dna.structuredContent.content) {
            try {
                let parsed = JSON.parse(dna.structuredContent.content);
                if (Array.isArray(parsed) && parsed.length > 0) dna = parsed[0];
                else dna = parsed;
            } catch(e) {}
        } else if (Array.isArray(dna) && dna.length > 0) {
            dna = dna[0];
        }

        // Simple heuristic for badge
        const dnaStr = JSON.stringify(dna).toLowerCase();
        if (dnaStr.includes("cobol") || dnaStr.includes("mainframe") || dnaStr.includes("jcl")) {
            document.getElementById("mf-badge").innerHTML = '<span class="dot" style="background:#e44d5e;"></span> Mainframe tech: Detected';
            document.getElementById("mf-badge").style.borderColor = "#e44d5e";
        } else {
            document.getElementById("mf-badge").innerHTML = '<span class="dot" style="background:#10b981;"></span> Mainframe tech: Not detected';
            document.getElementById("mf-badge").style.borderColor = "#10b981";
        }
        
        detailsBox.innerHTML = renderDNA(dna);
    } catch (err) {
        detailsBox.innerHTML = `<p style="color: #ff6b6b;">Error: ${err.message}</p>`;
        document.getElementById("mf-badge").innerHTML = '<span class="dot"></span> Unknown';
    }
}

function renderDNA(dna) {
    if (!dna || typeof dna !== 'object') {
        return `<p style="color:#a39eb8;">No structural DNA profile available.</p>`;
    }
    
    let html = '';
    
    // Parse Top-level scalars
    let scalars = [];
    for (const [k, v] of Object.entries(dna)) {
        if (typeof v !== 'object') {
            scalars.push({ key: k, value: v });
        }
    }
    
    if (scalars.length > 0) {
        html += `<div class="dna-section-header">Core Metrics</div>`;
        scalars.forEach(s => {
            let mappedKey = s.key.replace(/_/g, ' ');
        if (mappedKey === "nb LOC") mappedKey = "LoC #";
        if (mappedKey === "nb elements") mappedKey = "Elements #";
        if (mappedKey === "nb interactions") mappedKey = "Interactions #";
        
        html += `
            <div class="dna-kv-pair">
                <span class="dna-k">${mappedKey}</span>
                <span class="dna-v">${s.value === "" ? "N/A" : s.value}</span>
            </div>
        `;
        });
    }

    // Sensitivity Levels
    let sens = dna.Data_Sentitivity_levels || dna.Data_Sensitivity_levels;
    if (sens && Array.isArray(sens) && sens.length > 0) {
        html += `<div class="dna-section-header">Data Sensitivity</div>`;
        html += `<div class="dna-tag-container">`;
        sens.forEach(t => {
            html += `<span class="dna-tag sensitive">${t}</span>`;
        });
        html += `</div>`;
    }

    // Element Types
    if (dna.element_types && Array.isArray(dna.element_types) && dna.element_types.length > 0) {
        html += `<div class="dna-section-header">Detected Element Types (${dna.element_types.length})</div>`;
        html += `<div class="dna-tag-container">`;
        dna.element_types.forEach(t => {
            html += `<span class="dna-tag">${t}</span>`;
        });
        html += `</div>`;
    }

    // Fallback: If it doesn't match standard keys, loop arrays
    for (const [k, v] of Object.entries(dna)) {
        if (k !== 'element_types' && k !== 'Data_Sentitivity_levels' && k !== 'Data_Sensitivity_levels' && Array.isArray(v) && v.length > 0) {
            html += `<div class="dna-section-header">${k.replace(/_/g, ' ')} (${v.length})</div>`;
            html += `<div class="dna-tag-container">`;
            v.forEach(t => {
                html += `<span class="dna-tag">${typeof t === 'object' ? JSON.stringify(t) : t}</span>`;
            });
            html += `</div>`;
        }
    }

    return html;
}

function nextStep(currentStep) {
    const input = document.querySelector(`#step-${currentStep} input, #step-${currentStep} select`);
    if (input && input.value.trim() === "") {
        alert("Please fill in the required field.");
        return;
    }
    
    document.getElementById(`step-${currentStep}`).classList.remove("active");
    const next = document.getElementById(`step-${currentStep + 1}`);
    if (next) {
        next.classList.add("active");
    }
}

document.getElementById("wizard-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    
    if (!selectedAppId) {
        alert("Please select an application first.");
        return;
    }
    
    const s = getSettings();
    const payload = {
        app_id: selectedAppId,
        goal: document.getElementById("goal").value,
        target_framework: document.getElementById("target_framework").value,
        compliance: document.getElementById("compliance").value,
        risk_profile: document.getElementById("risk_profile").value,
        refactoring_depth: document.getElementById("refactoring_depth").value,
        review_protocol: document.getElementById("review_protocol").value,
        mcp_url: s.mcp_url,
        mcp_key: s.mcp_key,
        llm_provider: s.llm_provider,
        llm_key: s.llm_key
    };
    
    document.getElementById("live-dashboard").classList.remove("hidden");
    document.getElementById("terminal").innerHTML = '<p class="sys-msg">Initializing Mission...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/analyze/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Failed to start mission");
        
        const data = await response.json();
        startSSEStream(data.job_id);
    } catch (err) {
        logTerminal(`Error: ${err.message}`, true);
    }
});

function logTerminal(msg, isError = false) {
    const term = document.getElementById("terminal");
    const p = document.createElement("p");
    p.className = isError ? "sys-msg" : "agent-msg";
    if (isError) p.style.color = "red";
    p.textContent = msg;
    term.appendChild(p);
    term.scrollTop = term.scrollHeight;
}

function startSSEStream(jobId) {
    const evtSource = new EventSource(`${API_BASE}/analyze/stream/${jobId}`);
    
    evtSource.onmessage = function(e) {
        logTerminal(e.data);
    };
    
    evtSource.addEventListener("complete", function(e) {
        const report = JSON.parse(e.data);
        evtSource.close();
        logTerminal("Mission Complete. Generating report...", false);
        displayReport(report, jobId);
    });
    
    evtSource.addEventListener("error", function(e) {
        if (e.data) {
            logTerminal(e.data, true);
        }
        evtSource.close();
    });
}

function displayReport(report, jobId) {
    const section = document.getElementById("report-section");
    const content = document.getElementById("report-content");
    section.classList.remove("hidden");
    
    // Very basic markdown to HTML for demo
    const md = `${report.executive_summary}\n\n${report.architecture_insights}\n\n${report.modernization_roadmap}\n\n${report.iso_5055_flaws}`;
    
    content.innerHTML = md.replace(/\n/g, '<br>').replace(/## (.*?)<br>/g, '<h2>$1</h2>').replace(/# (.*?)<br>/g, '<h1>$1</h1>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    document.getElementById("download-btn").onclick = async () => {
        // Trigger docx generation backend endpoint
        window.open(`${API_BASE}/report/download/${jobId}`, "_blank");
    };
}
