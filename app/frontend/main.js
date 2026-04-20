const API_BASE = ""; // Relative paths so it dynamically uses localhost or Docker IP

let selectedAppId = null;
let isMissionRunning = false;

function setControlsDisabled(disabled) {
    isMissionRunning = !!disabled;
    try {
        const submitBtn = document.querySelector('#wizard-form button[type="submit"]');
        if (submitBtn) submitBtn.disabled = disabled;
        const formEls = document.querySelectorAll('#wizard-form input, #wizard-form select, #wizard-form textarea, #wizard-form button');
        formEls.forEach(el => {
            if (el && el.type === "submit") return;
            el.disabled = disabled;
        });
        const appRadios = document.querySelectorAll('input[name="app_selection"]');
        appRadios.forEach(r => { r.disabled = disabled; });
        const settingsBtn = document.getElementById("settings-btn");
        if (settingsBtn) settingsBtn.disabled = disabled;
    } catch {}
}

const GOAL_TO_TYPES = {
    "mono-to-micro": [
        "Domain-driven service boundaries",
        "Strangler fig decomposition",
        "API-first extraction",
        "Event-driven split",
    ],
    "refactoring": [
        "Code cleanup and modularization",
        "Performance refactoring",
        "Security hardening refactor",
    ],
    "re-architect": [
        "Microservices reference architecture",
        "Event-driven architecture",
        "Layered re-architecture",
    ],
    "re-platform": [
        "Container platform migration",
        "PaaS modernization",
        "Managed database + runtime",
    ],
    "re-write": [
        "Incremental rewrite",
        "Greenfield rewrite",
        "Rewrite with strangler pattern",
    ],
    "re-write-mainframe": [
        "Rewrite to cloud-native batch",
        "Encapsulate via APIs",
        "Lift and shift",
    ],
};

function getSelectedCriteria() {
    const ids = ["crit_structural_flaws", "crit_iso_5055", "crit_cve", "crit_cloud", "crit_green"];
    const out = [];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.checked) out.push(el.value);
    });
    if (!out.includes("structural-flaws")) out.unshift("structural-flaws");
    return Array.from(new Set(out));
}

function ensureAtLeastOneCriteriaSelected() {
    const ids = ["crit_structural_flaws", "crit_iso_5055", "crit_cve", "crit_cloud", "crit_green"];
    const anyChecked = ids.some(id => {
        const el = document.getElementById(id);
        return !!(el && el.checked);
    });
    if (!anyChecked) {
        const structural = document.getElementById("crit_structural_flaws");
        if (structural) structural.checked = true;
    }
}

function applyCriteriaDefaultsFromRiskProfile() {
    const risk = document.getElementById("selRiskProfile")?.value || "";
    const structural = document.getElementById("crit_structural_flaws");
    if (structural) structural.checked = true;

    const iso = document.getElementById("crit_iso_5055");
    const cve = document.getElementById("crit_cve");

    if (iso) iso.checked = false;
    if (cve) cve.checked = false;

    if (risk === "ISO-5055 only" || risk === "Performance") {
        if (iso) iso.checked = true;
    } else if (risk === "Security") {
        if (cve) cve.checked = true;
    } else if (risk === "Performance and Security") {
        if (iso) iso.checked = true;
        if (cve) cve.checked = true;
    }
    ensureAtLeastOneCriteriaSelected();
}

function updateModernizationTypeOptions() {
    const goal = document.getElementById("selGoal")?.value || "";
    const sel = document.getElementById("selModernizationType");
    if (!sel) return;

    const types = GOAL_TO_TYPES[goal] || [];
    sel.innerHTML = "";
    if (types.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Select a modernization goal first";
        sel.appendChild(opt);
        sel.disabled = true;
        return;
    }
    sel.disabled = false;
    types.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        sel.appendChild(opt);
    });
}

async function loadAdvisorsForApp(appId) {
    const sel = document.getElementById("selAdvisor");
    if (!sel) return;
    sel.innerHTML = '<option value="">Loading advisors...</option>';
    try {
        const res = await fetch(`${API_BASE}/advisors?app_id=${encodeURIComponent(appId)}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Failed to fetch advisors");
        const data = await res.json();
        const items = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
        sel.innerHTML = '<option value="">None</option>';
        items.forEach(a => {
            if (!a) return;
            const id = typeof a === "string" ? a : (a.id || a.advisor_id || a.advisorId || "");
            const name = typeof a === "string" ? a : (a.name || a.displayName || a.title || id);
            if (!id && !name) return;
            const opt = document.createElement("option");
            opt.value = id || name;
            opt.textContent = name || id;
            sel.appendChild(opt);
        });
    } catch {
        sel.innerHTML = '<option value="">None (unable to load)</option>';
    }
}

function isDebug() {
    try {
        const q = new URLSearchParams(window.location.search);
        if (q.get("debug") === "1") return true;
    } catch {}
    return localStorage.getItem("UI_DEBUG") === "1";
}

function debugLog(...args) {
    try {
        console.log("[UI-DEBUG]", ...args);
        const panel = document.getElementById("debug-panel");
        const logEl = document.getElementById("debug-log");
        if (panel && logEl && (isDebug() || window.__forceShowDebug)) {
            panel.style.display = "block";
            const line = args.map(a => {
                try { return typeof a === "string" ? a : JSON.stringify(a); }
                catch { return String(a); }
            }).join(" ");
            logEl.textContent += `${new Date().toISOString()} ${line}\n`;
            logEl.scrollTop = logEl.scrollHeight;
        }
    } catch {}
}

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
    if (s.llm_provider) headers['x-llm-provider'] = s.llm_provider;
    if (s.llm_key) headers['x-llm-key'] = s.llm_key;
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
        const sap = localStorage.getItem('cfg_searchapi_key') || "";
        const sapInput = document.getElementById("cfg_searchapi_key");
        if (sapInput) sapInput.value = sap;
        modal.classList.remove("hidden");
    };
    document.getElementById("close-settings").onclick = () => modal.classList.add("hidden");
    
    document.getElementById("save-settings-btn").onclick = () => {
        localStorage.setItem('cfg_mcp_url', document.getElementById("cfg_mcp_url").value.trim());
        localStorage.setItem('cfg_mcp_key', document.getElementById("cfg_mcp_key").value.trim());
        localStorage.setItem('cfg_llm_provider', document.getElementById("cfg_llm_provider").value);
        localStorage.setItem('cfg_llm_key', document.getElementById("cfg_llm_key").value.trim());
        const sapInput = document.getElementById("cfg_searchapi_key");
        if (sapInput) localStorage.setItem('cfg_searchapi_key', sapInput.value.trim());
        modal.classList.add("hidden");
        updateMCPLabel();
        loadApplications();
    };

    document.getElementById("clear-settings-btn").onclick = () => {
        localStorage.removeItem('cfg_mcp_url');
        localStorage.removeItem('cfg_mcp_key');
        localStorage.removeItem('cfg_llm_provider');
        localStorage.removeItem('cfg_llm_key');
        localStorage.removeItem('cfg_searchapi_key');
        document.getElementById("cfg_mcp_url").value = "";
        document.getElementById("cfg_mcp_key").value = "";
        document.getElementById("cfg_llm_provider").value = "openrouter";
        document.getElementById("cfg_llm_key").value = "";
        const sapInput = document.getElementById("cfg_searchapi_key");
        if (sapInput) sapInput.value = "";
        modal.classList.add("hidden");
        updateMCPLabel();
        loadApplications();
    };

    await loadApplications();
});

async function loadApplications() {
    try {
        const settings = getSettings();
        if (!settings.mcp_key) {
            try {
                const cfgRes = await fetch(`${API_BASE}/config`);
                if (cfgRes.ok) {
                    const cfg = await cfgRes.json();
                    if (!cfg.server_has_mcp_key) {
                        document.getElementById("status-text").textContent = `Missing CAST MCP credentials (open Settings)`;
                        const listContainer = document.getElementById("app-list");
                        listContainer.innerHTML = '<p style="padding: 1rem; color: #a39eb8;">Set CAST MCP URL and X-API-KEY in Settings to load applications.</p>';
                        return;
                    }
                }
            } catch (e) {}
        }
        document.getElementById("status-text").textContent = `Loading applications...`;
        const res = await fetch(`${API_BASE}/applications`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Failed to fetch applications");
        let apps = await res.json();
        debugLog("Raw /applications type:", Array.isArray(apps) ? "array" : typeof apps, "keys:", apps && !Array.isArray(apps) ? Object.keys(apps) : []);

        const tryParseArrayString = (s) => {
            if (typeof s !== "string") return null;
            try {
                const a = JSON.parse(s);
                if (Array.isArray(a)) return a;
            } catch {}
            try {
                const s1 = s.replace(/\\n/g, '\n');
                const a = JSON.parse(s1);
                if (Array.isArray(a)) return a;
            } catch {}
            try {
                const m = s.match(/\[[\s\S]*\]/m);
                if (m) {
                    const a = JSON.parse(m[0]);
                    if (Array.isArray(a)) return a;
                }
            } catch {}
            return null;
        };
        
        // Handle the new nested meta/content/isError payload structure
        if (apps && apps.content && Array.isArray(apps.content) && apps.content.length > 0) {
            let innerContent = apps.content[0];
            if (innerContent.type === 'text' && innerContent.text) {
                try {
                    let parsedText = JSON.parse(innerContent.text);
                    if (parsedText.content) {
                        const arr = tryParseArrayString(parsedText.content);
                        if (arr) {
                            apps = arr;
                            debugLog("Parsed from content[0].text -> content length:", apps.length);
                        }
                    }
                } catch (e) {
                    console.error("Failed parsing inner text:", e);
                    debugLog("Parse error content[0].text:", String(e));
                }
            }
        }
        // Always attempt structuredContent as a fallback if result is not an array yet
        if (!Array.isArray(apps) && apps && apps.structuredContent && apps.structuredContent.content) {
            try {
                const arr = tryParseArrayString(apps.structuredContent.content);
                if (arr) {
                    apps = arr;
                    debugLog("Parsed from structuredContent.content -> content length:", apps.length);
                }
            } catch (e) {
                console.error("Failed parsing structuredContent:", e);
                debugLog("Parse error structuredContent:", String(e));
            }
        }
        
        if (!Array.isArray(apps)) apps = [];

        document.getElementById("status-text").textContent = `Loaded ${apps.length} applications`;
        debugLog("Final apps length:", apps.length, "first item:", apps[0]);
        
        const listContainer = document.getElementById("app-list");
        listContainer.innerHTML = '';
        
        if (apps.length === 0) {
            listContainer.innerHTML = '<p style="padding: 1rem; color: #a39eb8;">No applications found.</p>';
            window.__forceShowDebug = true;
            debugLog("No apps to render; showing debug panel.");
            return;
        }

        const typeWriter = (el, text, delay = 20) => {
            el.textContent = '';
            let i = 0;
            const timer = setInterval(() => {
                if (i < text.length) {
                    el.textContent += text.charAt(i++);
                } else {
                    clearInterval(timer);
                }
            }, delay);
        };

        apps.forEach((app, index) => {
            const name = typeof app === 'string' ? app : (app.name || app.id || "Unknown App");
            const id = typeof app === 'string' ? app : (app.id || name);
            
            const label = document.createElement("label");
            label.className = "app-item";
            label.innerHTML = `
                <input type="radio" name="app_selection" value="${id}">
                <span style="font-weight:bold;"></span>
            `;
            
            label.querySelector("input").addEventListener("change", (e) => {
                if (e.target.checked) {
                    selectedAppId = e.target.value;
                    loadDNA(selectedAppId);
                    document.getElementById("mission-scoping").classList.remove("hidden");
                    updateModernizationTypeOptions();
                    applyCriteriaDefaultsFromRiskProfile();
                    loadAdvisorsForApp(selectedAppId);
                }
            });
            
            listContainer.appendChild(label);
            // Animate the visible name without hiding the label
            const span = label.querySelector("span");
            // small stagger so multiple items animate sequentially
            setTimeout(() => typeWriter(span, name, 18), index * 80);
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

        const tryParseJSON = (v) => {
            if (typeof v !== "string") return null;
            const s0 = v.trim();
            if (!s0) return null;
            const candidates = [
                s0,
                s0.replace(/\\n/g, "\n"),
                s0.replace(/\\r/g, "\r"),
                s0.replace(/\\n/g, "\n").replace(/\\r/g, "\r"),
                s0.replace(/\\"/g, "\""),
                s0.replace(/\\"/g, "\"").replace(/\\n/g, "\n").replace(/\\r/g, "\r"),
            ];
            for (const s of candidates) {
                try { return JSON.parse(s); } catch {}
                try {
                    const s2 = s.replace(/\\(?!["\\/bfnrtu])/g, "\\\\").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
                    return JSON.parse(s2);
                } catch {}
            }
            try {
                const m = s0.match(/\[[\s\S]*\]|\{[\s\S]*\}/);
                if (m && m[0]) {
                    const s3 = m[0].replace(/\\(?!["\\/bfnrtu])/g, "\\\\").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
                    return JSON.parse(s3);
                }
            } catch {}
            return null;
        };

        const normalizeDNA = (raw) => {
            let cur = raw;
            for (let i = 0; i < 4; i++) {
                if (typeof cur === "string") {
                    const parsed = tryParseJSON(cur);
                    if (parsed == null) break;
                    cur = parsed;
                    continue;
                }
                if (Array.isArray(cur)) {
                    cur = cur.length > 0 ? cur[0] : {};
                    continue;
                }
                if (cur && typeof cur === "object") {
                    if (cur.structuredContent && typeof cur.structuredContent.content === "string") {
                        const parsed = tryParseJSON(cur.structuredContent.content);
                        if (parsed != null) { cur = parsed; continue; }
                    }
                    if (typeof cur.content === "string") {
                        const meta = { ...cur };
                        delete meta.content;
                        const parsed = tryParseJSON(cur.content);
                        if (parsed != null) {
                            cur = parsed;
                            if (Array.isArray(cur)) cur = cur.length > 0 ? cur[0] : {};
                            if (cur && typeof cur === "object") {
                                for (const [k, v] of Object.entries(meta)) {
                                    if (cur[k] == null) cur[k] = v;
                                }
                            }
                            continue;
                        }
                    }
                    if (Array.isArray(cur.content) && cur.content.length > 0) {
                        const first = cur.content[0];
                        if (first && typeof first === "object" && first.type === "text" && typeof first.text === "string") {
                            const parsed = tryParseJSON(first.text);
                            if (parsed != null) { cur = parsed; continue; }
                        }
                    }
                    if (cur && typeof cur === "object" && typeof cur.content === "object" && cur.content && typeof cur.content.content === "string") {
                        const parsed = tryParseJSON(cur.content.content);
                        if (parsed != null) { cur = parsed; continue; }
                    }
                    break;
                }
                break;
            }
            if (Array.isArray(cur)) cur = cur.length > 0 ? cur[0] : {};
            if (!cur || typeof cur !== "object") return {};
            if (cur && typeof cur === "object" && typeof cur.content === "string") {
                const parsed = tryParseJSON(cur.content);
                if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === "object") return parsed[0];
            }
            return cur;
        };

        const inferMainframe = (obj) => {
            if (!obj || typeof obj !== "object") return false;
            if (typeof obj.mainframe === "boolean") return obj.mainframe;
            if (typeof obj.mainframe_detected === "boolean") return obj.mainframe_detected;
            if (obj.platforms && typeof obj.platforms === "object" && typeof obj.platforms.mainframe === "boolean") return obj.platforms.mainframe;
            const keywords = [
                "mainframe",
                "cobol",
                "jcl",
                "cics",
                "ims",
                "db2",
                "vsam",
                "z/os",
                "zos",
                "pl/i",
                "pli",
                "pl1",
                "natural",
                "adabas",
                "rpg",
                "as/400",
                "as400",
                "ibm i",
                "ibm z"
            ];
            const scanList = (list) => {
                if (!Array.isArray(list)) return false;
                return list.some(item => typeof item === "string" && keywords.some(kw => item.toLowerCase().includes(kw)));
            };
            if (scanList(obj.element_types)) return true;
            if (scanList(obj.technologies)) return true;
            if (obj.technologies && typeof obj.technologies === "object") {
                for (const v of Object.values(obj.technologies)) {
                    if (scanList(v)) return true;
                }
            }
            return false;
        };

        dna = normalizeDNA(dna);

        const mfSection = document.getElementById("mainframeSection");
        if (inferMainframe(dna)) {
            document.getElementById("mf-badge").innerHTML = '<span class="dot" style="background:#e44d5e;"></span> Mainframe tech: Detected';
            document.getElementById("mf-badge").style.borderColor = "#e44d5e";
            if (mfSection) mfSection.style.display = "block";
        } else {
            document.getElementById("mf-badge").innerHTML = '<span class="dot" style="background:#10b981;"></span> Mainframe tech: Not detected';
            document.getElementById("mf-badge").style.borderColor = "#10b981";
            if (mfSection) mfSection.style.display = "none";
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
    
    const cleaned = { ...dna };
    const appName = typeof cleaned.name === "string" && cleaned.name ? cleaned.name : (typeof cleaned.application === "string" ? cleaned.application : "");
    if (typeof cleaned.application === "string" && typeof cleaned.name === "string" && cleaned.application === cleaned.name) {
        delete cleaned.application;
    }
    if (typeof cleaned.mainframe === "boolean") {
        delete cleaned.mainframe;
    }
    if (typeof cleaned.description === "string") {
        delete cleaned.description;
    }
    if (cleaned.CRUD_interactions != null) {
        delete cleaned.CRUD_interactions;
    }

    let html = '';
    
    // Parse Top-level scalars
    let scalars = [];
    const skipKeys = new Set(["content", "description", "CRUD_interactions"]);
    const preferredOrder = ["name", "nb_loc", "nb_LOC", "nb_elements", "nb_interactions"];

    const pushScalar = (k, v) => {
        if (skipKeys.has(k)) return;
        if (k === "application" && appName) return;
        if (k === "nb_LOC" && cleaned.nb_loc != null) return;
        if (typeof v !== "object") scalars.push({ key: k, value: v });
    };

    for (const k of preferredOrder) {
        if (Object.prototype.hasOwnProperty.call(cleaned, k)) {
            pushScalar(k, cleaned[k]);
        }
    }

    for (const [k, v] of Object.entries(cleaned)) {
        if (k === "content") continue;
        if (preferredOrder.includes(k)) continue;
        pushScalar(k, v);
    }
    
    if (scalars.length > 0) {
        html += `<div class="dna-section-header">Core Metrics</div>`;
        scalars.forEach(s => {
            let mappedKey = s.key.replace(/_/g, ' ');
        if (mappedKey === "nb LOC") mappedKey = "LoC #";
        if (mappedKey === "nb elements") mappedKey = "Elements #";
        if (mappedKey === "nb interactions") mappedKey = "Interactions #";
        if (mappedKey === "name" && appName) mappedKey = "Application";
        if (mappedKey === "nb loc") mappedKey = "LoC #";

        let displayValue = s.value;
        if (typeof displayValue === "string" && displayValue.length > 220) {
            displayValue = displayValue.slice(0, 220) + "…";
        }
        
        html += `
            <div class="dna-kv-pair">
                <span class="dna-k">${mappedKey}</span>
                <span class="dna-v">${displayValue === "" ? "N/A" : displayValue}</span>
            </div>
        `;
        });
    }

    // Sensitivity Levels
    let sens = cleaned.Data_Sentitivity_levels || cleaned.Data_Sensitivity_levels;
    if (sens && Array.isArray(sens) && sens.length > 0) {
        html += `<div class="dna-section-header">Data Sensitivity</div>`;
        html += `<div class="dna-tag-container">`;
        sens.forEach(t => {
            html += `<span class="dna-tag sensitive">${t}</span>`;
        });
        html += `</div>`;
    }

    // Technologies
    const tech = cleaned.technologies;
    if (tech && Array.isArray(tech) && tech.length > 0) {
        html += `<div class="dna-section-header">Technologies (${tech.length})</div>`;
        html += `<div class="dna-tag-container">`;
        tech.forEach(t => {
            html += `<span class="dna-tag">${t}</span>`;
        });
        html += `</div>`;
    } else if (tech && typeof tech === "object" && !Array.isArray(tech)) {
        const all = [];
        for (const v of Object.values(tech)) {
            if (Array.isArray(v)) all.push(...v);
        }
        if (all.length > 0) {
            html += `<div class="dna-section-header">Technologies (${all.length})</div>`;
            html += `<div class="dna-tag-container">`;
            all.forEach(t => {
                html += `<span class="dna-tag">${typeof t === "object" ? JSON.stringify(t) : t}</span>`;
            });
            html += `</div>`;
        }
    }

    // Element Types
    if (cleaned.element_types && Array.isArray(cleaned.element_types) && cleaned.element_types.length > 0) {
        html += `<div class="dna-section-header">Detected Element Types (${cleaned.element_types.length})</div>`;
        html += `<div class="dna-tag-container">`;
        cleaned.element_types.forEach(t => {
            html += `<span class="dna-tag">${t}</span>`;
        });
        html += `</div>`;
    }

    // Fallback: If it doesn't match standard keys, loop arrays
    for (const [k, v] of Object.entries(cleaned)) {
        if (k !== 'element_types' && k !== 'technologies' && k !== 'Data_Sentitivity_levels' && k !== 'Data_Sensitivity_levels' && Array.isArray(v) && v.length > 0) {
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

try {
    const goalEl = document.getElementById("selGoal");
    if (goalEl) goalEl.addEventListener("change", () => {
        updateModernizationTypeOptions();
        const v = goalEl.value;
        const mfSection = document.getElementById("mainframeSection");
        if (mfSection) mfSection.style.display = (v === "re-write-mainframe") ? "block" : "none";
    });

    const riskEl = document.getElementById("selRiskProfile");
    if (riskEl) riskEl.addEventListener("change", () => applyCriteriaDefaultsFromRiskProfile());

    ["crit_structural_flaws", "crit_iso_5055", "crit_cve", "crit_cloud", "crit_green"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", () => ensureAtLeastOneCriteriaSelected());
    });

    updateModernizationTypeOptions();
    applyCriteriaDefaultsFromRiskProfile();
} catch {}

document.getElementById("wizard-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (isMissionRunning) return;
    
    if (!selectedAppId) {
        alert("Please select an application first.");
        return;
    }
    
    const s = getSettings();
        const chkStrategy = [];
    if(document.getElementById("chkContainerization").checked) chkStrategy.push("Containerization");
    if(document.getElementById("chkNonContainerization").checked) chkStrategy.push("Non-Containerization");

    const payload = {
        app_id: selectedAppId,
        objective: document.getElementById("txtObjective").value,
        modernization_goal: document.getElementById("selGoal").value,
        modernization_type: document.getElementById("selModernizationType") ? document.getElementById("selModernizationType").value : "",
        strategy: chkStrategy.join(", "),
        risk_profile: document.getElementById("selRiskProfile").value,
        criteria: getSelectedCriteria(),
        advisor_id: document.getElementById("selAdvisor") ? document.getElementById("selAdvisor").value : "",
        db_migration: document.getElementById("selDBMigration").value,
        rewrite_mainframe: document.getElementById("mainframeSection").style.display !== "none" ? document.getElementById("rewrite_mainframe").value : "",
        target_lang: document.getElementById("mainframeSection").style.display !== "none" ? document.getElementById("target_lang").value : "",
        mcp_url: s.mcp_url,
        mcp_key: s.mcp_key,
        llm_provider: s.llm_provider,
        llm_key: s.llm_key,
        searchapi_key: (localStorage.getItem('cfg_searchapi_key') || ""),
        use_llm: document.getElementById("chkUseLLM") ? document.getElementById("chkUseLLM").checked : false,
        include_locations: document.getElementById("chkIncludeLocations") ? document.getElementById("chkIncludeLocations").checked : false
    };
    
    document.getElementById("live-dashboard").classList.remove("hidden");
    document.getElementById("terminal").innerHTML = '<p class="sys-msg">Initializing Mission...</p>';
    setControlsDisabled(true);
    
    try {
        const response = await fetch(`${API_BASE}/kickoff`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            let msg = "Failed to start mission";
            try {
                const j = await response.json();
                if (j && j.detail) msg = j.detail;
            } catch {}
            throw new Error(msg);
        }
        
        const data = await response.json();
        startSSEStream(data.job_id);
    } catch (err) {
        logTerminal(`Error: ${err.message}`, true);
        setControlsDisabled(false);
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
        setControlsDisabled(false);
    });
    
    evtSource.addEventListener("error", function(e) {
        if (e.data) {
            logTerminal(e.data, true);
        }
        evtSource.close();
        setControlsDisabled(false);
    });

    evtSource.onerror = function() {
        logTerminal("Connection to server lost.", true);
        try { evtSource.close(); } catch {}
        setControlsDisabled(false);
    };
}

function displayReport(report, jobId) {
    const section = document.getElementById("report-section");
    const content = document.getElementById("report-content");
    section.classList.remove("hidden");

    const md = [
        report.executive_summary || "",
        report.architecture_insights || "",
        report.modernization_roadmap || "",
        report.iso_5055_flaws || "",
        report.disclaimer || ""
    ].filter(Boolean).join("\n\n");

    const escapeHtml = (s) => s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

    const lines = md.split(/\r?\n/);
    let i = 0;
    let htmlParts = [];

    const flushParagraph = (buf) => {
          const text = buf.join("\n").trim();
          if (!text) return;
          let h = text;

          // Normalize any LLM-generated HTML tags to markdown before escaping
          h = h.replace(/<\/?strong>/gi, '**');
          h = h.replace(/<\/?b>/gi, '**');

          // First, escape HTML for safety to prevent raw tags from breaking layout
          h = escapeHtml(h);

          // code fences
          h = h.replace(/```([\s\S]*?)```/g, '<pre style="background:#0b0d22; padding:1rem; border-radius:6px; overflow-x:auto;"><code>$1</code></pre>');
          // inline code
          h = h.replace(/`([^`]+)`/g, '<code style="background:#1a1c3b; padding:0.2rem 0.4rem; border-radius:3px; font-family:monospace; color:#00c4cc;">$1</code>');
          // headers
          h = h.replace(/^### (.*)$/gm, '<h3>$1</h3>');
          h = h.replace(/^## (.*)$/gm, '<h2>$1</h2>');
          h = h.replace(/^# (.*)$/gm, '<h1>$1</h1>');
          // bold
          h = h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
          // bullet lists
          h = h.replace(/^(?:\s*[-*+]\s+.*(?:\n|$))+?/gm, (block) => {
              const items = block.trim().split(/\n/).map(l => l.replace(/^\s*[-*+]\s+/, '').trim());
              return `<ul>${items.map(it => `<li>${it}</li>`).join('')}</ul>`;
          });
          htmlParts.push(h);
      };

      const renderTable = (rows) => {
          // Remove alignment row if present (---)
          if (rows.length > 1 && /^\|\s*:?-{3,}.*\|$/.test(rows[1].trim())) {
              rows.splice(1, 1);
          }
          const toCells = (r) => r.split('|').slice(1, -1).map(c => {
              let cell = c.trim();
              cell = cell.replace(/<\/?strong>/gi, '**');
              cell = cell.replace(/<\/?b>/gi, '**');
              cell = escapeHtml(cell);
              cell = cell.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
              cell = cell.replace(/`([^`]+)`/g, '<code>$1</code>');
              return cell;
          });
          const header = rows[0].split('|').slice(1, -1).map(c => {
              let cell = c.trim();
              cell = cell.replace(/<\/?strong>/gi, '**');
              cell = cell.replace(/<\/?b>/gi, '**');
              cell = escapeHtml(cell);
              cell = cell.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
              return cell;
          });
          const body = rows.slice(1).map(toCells);
          const th = header.map(h => `<th style="background:rgba(0,196,204,0.1); padding:0.8rem; text-transform:none; text-align:left; border-bottom:1px solid var(--glass-border);">${h || '-'}</th>`).join('');
          const tr = body.map(r => `<tr>${r.map(c => `<td style="padding:0.8rem; border-bottom:1px solid rgba(255,255,255,0.05);">${c || '-'}</td>`).join('')}</tr>`).join('');
          return `<div style="overflow-x:auto; margin:1rem 0;"><table style="width:100%; border-collapse:collapse; border:1px solid var(--glass-border);"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
      };

    while (i < lines.length) {
        // detect table block
        if (/^\|.*\|$/.test(lines[i].trim())) {
            const tbl = [];
            while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
                if (!lines[i].trim()) break;
                tbl.push(lines[i]);
                i++;
            }
            if (tbl.length >= 1) htmlParts.push(renderTable(tbl));
            continue;
        }
        // collect paragraph until blank or table start
        const buf = [];
        while (i < lines.length && lines[i].trim() !== '' && !/^\|.*\|$/.test(lines[i].trim())) {
            buf.push(lines[i]);
            i++;
        }
        flushParagraph(buf);
        // skip blank lines
        while (i < lines.length && lines[i].trim() === '') i++;
    }

    content.innerHTML = htmlParts.join('\n');

    document.getElementById("download-btn").onclick = async () => {
        window.open(`${API_BASE}/report/download/${jobId}`, "_blank");
    };
}
