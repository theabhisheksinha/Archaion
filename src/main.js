document.addEventListener("DOMContentLoaded", () => {
  const els = {
    portfolioList: document.getElementById("portfolio-list"),
    dnaBadge: document.getElementById("dna-badge"),
    dnaFlags: document.getElementById("dna-flags"),
    analyzeBtn: document.getElementById("analyze-btn"),
    downloadBtn: document.getElementById("download-btn"),
    apiBase: document.getElementById("api-base"),
    selectedPill: document.getElementById("selected-pill"),
    status: document.getElementById("status"),
    missionGrid: document.getElementById("mission-grid"),
    missionCtx: document.getElementById("mission-ctx"),
    cloudProvider: document.getElementById("cloud-provider"),
    dbMigration: document.getElementById("db-migration"),
    agentLog: document.getElementById("agent-log"),
    analysisSummary: document.getElementById("analysis-summary"),
    archInsights: document.getElementById("arch-insights"),
    roadmapViewer: document.getElementById("roadmap-viewer"),
    tabExec: document.getElementById("tab-exec"),
    tabArch: document.getElementById("tab-arch"),
    tabRoadmap: document.getElementById("tab-roadmap"),
    panelExec: document.getElementById("panel-exec"),
    panelArch: document.getElementById("panel-arch"),
    panelRoadmap: document.getElementById("panel-roadmap"),
  };

  const state = {
    selectedAppId: null,
    selectedAppName: null,
    lastAnalysis: null,
    missionConfig: {
      app_name: null,
      mission_type: null,
      cloud_provider: null,
      db_migration_requested: false,
    },
  };

  function getApiBase() {
    const stored = (localStorage.getItem("apiBase") || "").trim();
    if (stored) return stored.replace(/\/+$/, "");
    return "http://127.0.0.1:8000";
  }

  async function apiFetch(path, init) {
    const primary = getApiBase();
    const alternates = [];
    if (primary.includes("127.0.0.1")) alternates.push(primary.replace("127.0.0.1", "localhost"));
    if (primary.includes("localhost")) alternates.push(primary.replace("localhost", "127.0.0.1"));
    const bases = [primary, ...alternates.filter((v, i, a) => a.indexOf(v) === i)];
    let lastErr = null;
    for (const base of bases) {
      try {
        const url = `${base}${path}`;
        const res = await fetch(url, init);
        if (!res.ok) {
          const contentType = (res.headers.get("content-type") || "").toLowerCase();
          const isJson = contentType.includes("application/json");
          const body = isJson ? await res.json() : await res.text();
          const detail =
            typeof body === "string"
              ? body
              : body && typeof body === "object" && "detail" in body
                ? body.detail
                : JSON.stringify(body);
          throw new Error(`${res.status} ${detail}`);
        }
        const contentType = (res.headers.get("content-type") || "").toLowerCase();
        const isJson = contentType.includes("application/json");
        return isJson ? await res.json() : await res.text();
      } catch (e) {
        lastErr = e;
        continue;
      }
    }
    throw lastErr || new Error("Request failed");
  }

  function setText(el, text) {
    if (!el) return;
    el.textContent = text == null ? "" : String(text);
  }

  function setStatus(kind, text) {
    setText(els.status, text);
    const base = "rounded-2xl border bg-slate-950/40 p-4 text-sm backdrop-blur";
    if (kind === "error") {
      els.status.className = `${base} border-red-400/30 text-red-200`;
      return;
    }
    if (kind === "ok") {
      els.status.className = `${base} border-emerald-400/20 text-slate-200`;
      return;
    }
    els.status.className = `${base} border-white/10 text-slate-200`;
  }

  function setApiBaseDisplay() {
    setText(els.apiBase, getApiBase());
  }

  function toInt(value) {
    if (value == null) return null;
    if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
    if (typeof value === "string") {
      const s = value.trim();
      if (!s || ["n/a", "na", "none", "null"].includes(s.toLowerCase())) return null;
      const digits = s.replace(/[^0-9]/g, "");
      if (!digits) return null;
      const n = Number.parseInt(digits, 10);
      return Number.isFinite(n) ? n : null;
    }
    return null;
  }

  function formatInt(value) {
    const n = toInt(value);
    if (n == null) return null;
    return new Intl.NumberFormat(undefined).format(n);
  }

  function detectMainframeSignals(data) {
    const res = { mainframe: false, signals: [] };
    if (!data || typeof data !== "object") return res;
    if (Boolean(data.mainframe) || (data.platforms && typeof data.platforms === "object" && Boolean(data.platforms.mainframe))) {
      res.signals.push("platform flag");
    }
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
      "ibm z",
    ];
    const lists = [];
    if (Array.isArray(data.technologies)) lists.push(data.technologies);
    if (Array.isArray(data.element_types)) lists.push(data.element_types);
    if (data.technologies && typeof data.technologies === "object" && Array.isArray(data.technologies.languages)) {
      lists.push(data.technologies.languages);
    }
    const picked = new Set();
    for (const lst of lists) {
      for (const item of lst) {
        if (typeof item !== "string") continue;
        const s = item.toLowerCase();
        if (!keywords.some((k) => s.includes(k))) continue;
        const label = item.trim();
        if (!label) continue;
        picked.add(label);
        if (picked.size >= 6) break;
      }
      if (picked.size >= 6) break;
    }
    res.signals.push(...Array.from(picked));
    res.mainframe = res.signals.length > 0;
    return res;
  }

  function currentAppLabel() {
    return state.selectedAppName || state.selectedAppId || "";
  }

  function renderSelectedPill() {
    const label = currentAppLabel();
    if (!label) {
      els.selectedPill.classList.add("hidden");
      els.selectedPill.textContent = "";
      return;
    }
    els.selectedPill.classList.remove("hidden");
    els.selectedPill.textContent = `Selected: ${label}`;
  }

  function renderFlags({ mainframe }) {
    els.dnaFlags.innerHTML = "";
    const badge = document.createElement("div");
    badge.className = `pill ${mainframe ? "pill--yes" : "pill--no"}`;
    badge.innerHTML = `<span class="pill__dot"></span><span>${mainframe ? "Mainframe tech: Detected" : "Mainframe tech: Not detected"}</span>`;
    els.dnaFlags.appendChild(badge);
  }

  function renderTechChips(technologies) {
    const items = Array.isArray(technologies) ? technologies.filter((t) => typeof t === "string" && t.trim()) : [];
    const max = 10;
    const shown = items.slice(0, max);
    const extra = items.length - shown.length;
    const chips = shown.map(
      (t) => `<span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-slate-200">${t}</span>`
    );
    if (extra > 0) {
      chips.push(`<span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-slate-300">+${extra}</span>`);
    }
    return chips.join(" ");
  }

  function renderDnaBadge(payload) {
    if (!payload) {
      els.dnaBadge.innerHTML = '<div class="text-sm text-slate-300">Select an application to view its DNA.</div>';
      renderFlags({ mainframe: false });
      return;
    }
    const data = Array.isArray(payload) ? payload[0] : payload;
    if (!data || typeof data !== "object") {
      els.dnaBadge.innerHTML = '<div class="text-sm text-slate-300">No DNA data available.</div>';
      renderFlags({ mainframe: false });
      return;
    }
    const name = data.name || data.app_id || currentAppLabel();
    const locRaw = data.nb_LOC ?? data.nb_LOC_value ?? data.nb_loc ?? data.loc;
    const elementsRaw = data.nb_elements ?? data.elements;
    const interactionsRaw = data.nb_interactions ?? data.interactions;
    const locText = formatInt(locRaw) ?? (typeof locRaw === "string" ? locRaw : "N/A");
    const elementsText = formatInt(elementsRaw) ?? (typeof elementsRaw === "string" ? elementsRaw : "N/A");
    const interactionsText = formatInt(interactionsRaw) ?? (typeof interactionsRaw === "string" ? interactionsRaw : "N/A");
    const technologies = Array.isArray(data.technologies) ? data.technologies : [];
    const mf = detectMainframeSignals(data);
    const mainframe = mf.mainframe;
    renderFlags({ mainframe });
    const signalText =
      mainframe && mf.signals.length
        ? `Detected from: ${mf.signals.slice(0, 3).join(", ")}`
        : "No COBOL/JCL/CICS/IMS/DB2/z/OS indicators found in the application DNA.";
    els.dnaBadge.innerHTML = `
      <div class="flex flex-col gap-4">
        <div class="flex flex-col gap-1">
          <div class="text-base font-medium text-slate-100 truncate">${name}</div>
          <div class="text-xs text-slate-300">${signalText}</div>
          <div class="flex flex-wrap gap-2 text-xs text-slate-300">
            <div class="rounded-lg border border-white/10 bg-white/5 px-2 py-1">LOC: <span class="text-slate-100">${locText}</span></div>
            <div class="rounded-lg border border-white/10 bg-white/5 px-2 py-1">Elements: <span class="text-slate-100">${elementsText}</span></div>
            <div class="rounded-lg border border-white/10 bg-white/5 px-2 py-1">Interactions: <span class="text-slate-100">${interactionsText}</span></div>
          </div>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-200">Technologies</div>
          <div class="mt-2 flex flex-wrap gap-2">${renderTechChips(technologies) || '<span class="text-xs text-slate-300">N/A</span>'}</div>
        </div>
      </div>
    `;
  }

  function renderPortfolio(apps) {
    els.portfolioList.innerHTML = "";
    if (!Array.isArray(apps) || apps.length === 0) {
      els.portfolioList.innerHTML = '<div class="text-sm text-slate-300">No applications found.</div>';
      return;
    }
    for (const app of apps) {
      const id = app && typeof app === "object" ? app.id || app.name : String(app);
      const name = app && typeof app === "object" ? app.name || app.id : String(app);
      if (!id) continue;
      const wrapper = document.createElement("label");
      wrapper.className = "flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2 text-sm text-slate-100 hover:border-white/20 hover:bg-slate-950/40";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "portfolio";
      radio.value = id;
      radio.className = "h-4 w-4 accent-fuchsia-400";
      radio.addEventListener("change", async () => {
        state.selectedAppId = id;
        state.selectedAppName = name;
        state.missionConfig.app_name = name || id;
        setLoading(false);
        renderSelectedPill();
        renderDnaBadge(null);
        try {
          const dna = await apiFetch(`/dna?app_id=${encodeURIComponent(id)}`);
          renderDnaBadge(dna);
        } catch (e) {
          renderDnaBadge({ name, error: String(e && e.message ? e.message : e) });
        }
      });
      const text = document.createElement("span");
      text.className = "min-w-0 flex-1 truncate";
      text.textContent = name;
      const meta = document.createElement("span");
      meta.className = "text-xs text-slate-400";
      meta.textContent = id;
      wrapper.appendChild(radio);
      wrapper.appendChild(text);
      wrapper.appendChild(meta);
      els.portfolioList.appendChild(wrapper);
    }
  }

  function extractMarkdown(data) {
    if (!data) return "";
    if (typeof data === "string") return data;
    if (Array.isArray(data)) return data.map(extractMarkdown).filter(Boolean).join("\n\n");
    if (typeof data === "object") {
      const candidates = ["markdown", "md", "report_md", "reportMarkdown", "content"];
      for (const k of candidates) {
        if (typeof data[k] === "string" && data[k].trim()) return data[k];
      }
      for (const v of Object.values(data)) {
        const found = extractMarkdown(v);
        if (found) return found;
      }
    }
    return "";
  }

  function pickText(obj, keys) {
    if (!obj || typeof obj !== "object") return "";
    for (const k of keys) {
      const v = obj[k];
      if (typeof v === "string" && v.trim()) return v;
      if (v && typeof v === "object") {
        const s = pickText(v, keys);
        if (s) return s;
      }
    }
    return "";
  }

  function downloadBlob(filename, contentType, text) {
    const blob = new Blob([text], { type: contentType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function setLoading(isLoading) {
    const needsCtx = state.missionConfig.mission_type === "cloud_transformation" || state.missionConfig.mission_type === "platform_modernization";
    const hasProvider = !!state.missionConfig.cloud_provider;
    const validMission = !!state.missionConfig.mission_type && (!needsCtx || hasProvider);
    els.analyzeBtn.disabled = isLoading || !state.selectedAppId || !validMission;
    els.analyzeBtn.textContent = isLoading ? "Analyzing..." : "Analyze";
  }

  function renderMissions() {
    const missions = [
      { id: "cloud_transformation", title: "Cloud Transformation", desc: "Migrate to cloud with minimal risk and quick wins." },
      { id: "platform_modernization", title: "Platform Modernization", desc: "Replatform core components for scalability and resilience." },
      { id: "architecture_design", title: "Architecture Design", desc: "Assess and redesign for future-ready architecture." },
      { id: "microservices_refactoring", title: "Microservices Refactoring", desc: "Break monoliths into modular services incrementally." },
    ];
    els.missionGrid.innerHTML = "";
    for (const m of missions) {
      const label = document.createElement("label");
      label.className = "flex cursor-pointer items-start gap-3 rounded-xl border border-white/10 bg-slate-950/30 p-3 text-sm text-slate-100 hover:border-white/20 hover:bg-slate-950/40";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "mission";
      radio.value = m.id;
      radio.className = "mt-1 h-4 w-4 accent-fuchsia-400";
      const wrapper = document.createElement("div");
      wrapper.className = "min-w-0 flex-1";
      const t = document.createElement("div");
      t.className = "truncate font-medium";
      t.textContent = m.title;
      const d = document.createElement("div");
      d.className = "mt-1 text-xs text-slate-300";
      d.textContent = m.desc;
      wrapper.appendChild(t);
      wrapper.appendChild(d);
      label.appendChild(radio);
      label.appendChild(wrapper);
      radio.addEventListener("change", () => {
        state.missionConfig.mission_type = m.id;
        updateCtxVisibility();
        setLoading(false);
      });
      els.missionGrid.appendChild(label);
    }
  }

  function updateCtxVisibility() {
    const needsCtx = state.missionConfig.mission_type === "cloud_transformation" || state.missionConfig.mission_type === "platform_modernization";
    if (needsCtx) {
      els.missionCtx.classList.remove("hidden");
    } else {
      els.missionCtx.classList.add("hidden");
      state.missionConfig.cloud_provider = null;
      state.missionConfig.db_migration_requested = false;
      if (els.cloudProvider) els.cloudProvider.value = "";
      if (els.dbMigration) els.dbMigration.checked = false;
    }
  }

  function mapMissionToCloudStrategy(cfg) {
    if (!cfg || !cfg.mission_type) return null;
    const provider = cfg.cloud_provider;
    if (cfg.mission_type === "cloud_transformation") {
      if (provider === "AWS") return "aws_lift_shift";
      if (provider === "Azure") return "azure_lift_shift";
      if (provider === "GCP") return "gcp_refactor";
      return "gcp_refactor";
    }
    if (cfg.mission_type === "platform_modernization") {
      if (provider === "AWS") return "aws_replatform";
      if (provider === "Azure") return "azure_replatform";
      if (provider === "GCP") return "gcp_refactor";
      return "gcp_refactor";
    }
    if (cfg.mission_type === "architecture_design") return "gcp_refactor";
    if (cfg.mission_type === "microservices_refactoring") return "gcp_refactor";
    return null;
  }

  function switchTab(which) {
    const map = {
      exec: { tab: els.tabExec, panel: els.panelExec },
      arch: { tab: els.tabArch, panel: els.panelArch },
      roadmap: { tab: els.tabRoadmap, panel: els.panelRoadmap },
    };
    for (const k of Object.keys(map)) {
      const t = map[k].tab;
      const p = map[k].panel;
      if (!t || !p) continue;
      const active = k === which;
      t.setAttribute("aria-selected", String(active));
      if (active) {
        p.removeAttribute("hidden");
      } else {
        p.setAttribute("hidden", "");
      }
    }
  }

  els.cloudProvider.addEventListener("change", () => {
    state.missionConfig.cloud_provider = els.cloudProvider.value || null;
    setLoading(false);
  });
  els.dbMigration.addEventListener("change", () => {
    state.missionConfig.db_migration_requested = !!els.dbMigration.checked;
  });

  els.tabExec.addEventListener("click", () => switchTab("exec"));
  els.tabArch.addEventListener("click", () => switchTab("arch"));
  els.tabRoadmap.addEventListener("click", () => switchTab("roadmap"));

  if (els.apiBase) {
    els.apiBase.title = "Click to change backend URL";
    els.apiBase.style.cursor = "pointer";
    els.apiBase.addEventListener("click", () => {
      const cur = getApiBase();
      const next = (prompt("Backend URL (e.g., http://127.0.0.1:8000)", cur) || "").trim();
      if (next && next !== cur) {
        localStorage.setItem("apiBase", next.replace(/\/+$/, ""));
        setApiBaseDisplay();
        // Reboot flow to refetch with new base
        boot();
      }
    });
  }

  window.addEventListener("error", (ev) => {
    const msg = ev && ev.message ? ev.message : "Script error";
    setStatus("error", msg);
  });

  window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev && "reason" in ev ? ev.reason : null;
    const msg =
      reason && typeof reason === "object" && "message" in reason
        ? reason.message
        : String(reason == null ? "Unhandled promise rejection" : reason);
    setStatus("error", msg);
  });

  els.analyzeBtn.addEventListener("click", async () => {
    const cfg = state.missionConfig;
    if (!state.selectedAppId || !cfg.mission_type) return;
    const strategy = mapMissionToCloudStrategy(cfg);
    const appLabel = currentAppLabel() || "application";
    const missionLabel = cfg.mission_type || "";
    const providerLabel = cfg.cloud_provider || "N/A";
    setLoading(true);
    setText(els.analysisSummary, "");
    setText(els.archInsights, "");
    setText(els.roadmapViewer, "");
    setText(els.agentLog, `Analyzing ${appLabel} using ${missionLabel}${cfg.cloud_provider ? ` on ${providerLabel}` : ""}…`);
    state.lastAnalysis = null;
    try {
      const res = await apiFetch("/analyze", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          app_id: state.selectedAppId,
          cloud_strategy: strategy,
          ...cfg,
        }),
      });
      state.lastAnalysis = res;
      const md = extractMarkdown(res);
      const execText = pickText(res, ["executive_summary", "summary"]) || md || JSON.stringify(res, null, 2);
      const archText = pickText(res, ["architecture", "architecture_insights", "insights"]) || md || JSON.stringify(res, null, 2);
      const roadmapText = pickText(res, ["roadmap", "modernization_roadmap"]) || md || JSON.stringify(res, null, 2);
      setText(els.analysisSummary, execText);
      setText(els.archInsights, archText);
      setText(els.roadmapViewer, roadmapText);
      setText(els.agentLog, `Analysis complete for ${appLabel} (${missionLabel}${cfg.cloud_provider ? `, ${providerLabel}` : ""}).`);
      switchTab("exec");
    } catch (e) {
      const msg = String(e && e.message ? e.message : e);
      setText(els.analysisSummary, msg);
      setText(els.agentLog, `Analysis failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  });

  els.downloadBtn.addEventListener("click", () => {
    const label = currentAppLabel() || "analysis";
    const md = extractMarkdown(state.lastAnalysis);
    if (md) {
      downloadBlob(`${label}-report.md`, "text/markdown;charset=utf-8", md);
      return;
    }
    const jsonText = state.lastAnalysis ? JSON.stringify(state.lastAnalysis, null, 2) : "";
    downloadBlob(`${label}-report.json`, "application/json;charset=utf-8", jsonText);
  });

  async function boot() {
    setLoading(false);
    setText(els.analysisSummary, "");
    setText(els.archInsights, "");
    setText(els.roadmapViewer, "");
    setApiBaseDisplay();
    renderSelectedPill();
    renderFlags({ mainframe: false });
    renderMissions();
    updateCtxVisibility();
    setStatus("info", "Loading applications…");
    try {
      const apps = await apiFetch("/applications");
      renderPortfolio(apps);
      setStatus("ok", `Loaded ${Array.isArray(apps) ? apps.length : 0} applications`);
    } catch (e) {
      els.portfolioList.innerHTML = `<div class="text-sm text-red-300">Failed to load applications: ${String(
        e && e.message ? e.message : e
      )}</div>`;
      setStatus("error", `Failed to load applications: ${String(e && e.message ? e.message : e)}`);
    }
  }

  boot();
});
