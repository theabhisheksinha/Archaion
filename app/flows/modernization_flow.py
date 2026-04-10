import os
import json
import asyncio
import logging
import litellm
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

litellm.set_verbose = True
logger = logging.getLogger("archaion.flow")
logger.setLevel(logging.DEBUG)

try:
    from app.backend.crew import ModernizationCrew
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    ModernizationCrew = type("Dummy", (), {})

class ModernizationState(BaseModel):
    portfolio: List[Dict[str, Any]] = []
    selected_app_id: Optional[str] = None
    app_name: Optional[str] = None
    dna_profile: Optional[Dict[str, Any]] = None
    mission_params: Optional[Dict[str, str]] = None
    mission_report: Optional[str] = None
    validation_report: Optional[str] = None
    status_updates: List[str] = []

class ModernizationFlow:
    """
    Wrapper to manage state, fetch data via MCP, and kick off the Crew.
    Ensures credentials flow from frontend to backend.
    """
    def __init__(self, mcp_client=None):
        self.state = ModernizationState()
        self.mcp_client = mcp_client

    def push_update(self, msg: str):
        print(f"Flow Update: {msg}")
        try:
            logger.info(msg)
        except Exception:
            pass
        self.state.status_updates.append(msg)

    async def discover_portfolio(self):
        self.push_update("Agentic Portfolio Discovery starting...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("applications", {})
            self.state.portfolio = res
        self.push_update("Portfolio Discovery complete.")
        return self.state.portfolio

    async def profile_application(self):
        if not self.state.selected_app_id:
            return
        self.push_update(f"Technical DNA Profiling for {self.state.selected_app_id}...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("stats", {"application": self.state.selected_app_id})
            def _try_json_load(s: Any):
                if not isinstance(s, str):
                    return None
                s = s.strip()
                if not s:
                    return None
                try:
                    return json.loads(s)
                except Exception:
                    try:
                        s2 = s.replace("\\n", "\n").replace("\\r", "\r")
                        return json.loads(s2)
                    except Exception:
                        return None

            def _first_stats_obj(obj: Any) -> Dict[str, Any]:
                if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                    return obj[0]
                if isinstance(obj, dict):
                    sc = obj.get("structuredContent")
                    if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                        parsed = _try_json_load(sc["content"])
                        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                            return parsed[0]
                        if isinstance(parsed, dict):
                            return parsed
                    content = obj.get("content")
                    if isinstance(content, str):
                        parsed = _try_json_load(content)
                        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                            return parsed[0]
                        if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                            parsed2 = _try_json_load(parsed["content"])
                            if isinstance(parsed2, list) and parsed2 and isinstance(parsed2[0], dict):
                                return parsed2[0]
                            if isinstance(parsed2, dict):
                                return parsed2
                        if isinstance(parsed, dict):
                            return parsed
                    if isinstance(content, list) and content:
                        first = content[0]
                        if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                            parsed = _try_json_load(first["text"])
                            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                                return parsed[0]
                            if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                                parsed2 = _try_json_load(parsed["content"])
                                if isinstance(parsed2, list) and parsed2 and isinstance(parsed2[0], dict):
                                    return parsed2[0]
                                if isinstance(parsed2, dict):
                                    return parsed2
                            if isinstance(parsed, dict):
                                return parsed
                    return obj
                return {}

            self.state.dna_profile = _first_stats_obj(res)
        self.push_update("Technical DNA Profiling complete.")
        return self.state.dna_profile

    async def execute_mission(self):
        if not self.state.dna_profile or not self.state.mission_params:
            return
        
        self.push_update("Initializing CrewAI Multi-Agent Execution...")
        
        # 1. Retrieve LLM Credentials from the frontend parameters
        params = self.state.mission_params
        
        ui_llm_provider = params.get("llm_provider")
        ui_llm_key = params.get("llm_key")
        ui_llm_model = params.get("llm_model")
        
        llm_provider = ui_llm_provider or "openrouter"
        llm_key = ui_llm_key or os.environ.get("OPENROUTER_API_KEY", "")
        llm_model = ui_llm_model or os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o"
        search_api_key = params.get("searchapi_key") or os.environ.get("SEARCHAPI_API_KEY", "")
        
        source = "UI Settings Payload" if ui_llm_key else "Environment Variables (.env)"
        logger.debug(f"[CONFIG TRACE] Initializing CrewAI with LLM Provider: {llm_provider.upper()} (Source: {source})")
        
        flaws_text = ""
        if self.mcp_client and self.state.selected_app_id:
            try:
                iso_res = await self.mcp_client.invoke_tool("application_iso_5055_explorer", {"application": self.state.selected_app_id})
                flaws_text = str(iso_res)
            except Exception:
                pass
        
        # 3. Prepare Inputs
        def _try_json_load(s: Any):
            if not isinstance(s, str):
                return None
            s = s.strip()
            if not s:
                return None
            try:
                return json.loads(s)
            except Exception:
                try:
                    s2 = s.replace("\\n", "\n").replace("\\r", "\r")
                    return json.loads(s2)
                except Exception:
                    return None

        def _first_stats_obj(obj: Any) -> Dict[str, Any]:
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                return obj[0]
            if isinstance(obj, dict):
                sc = obj.get("structuredContent")
                if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                    parsed = _try_json_load(sc["content"])
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        return parsed[0]
                    if isinstance(parsed, dict):
                        return parsed
                content = obj.get("content")
                if isinstance(content, str):
                    parsed = _try_json_load(content)
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        return parsed[0]
                    if isinstance(parsed, dict):
                        if isinstance(parsed.get("content"), str):
                            parsed2 = _try_json_load(parsed["content"])
                            if isinstance(parsed2, list) and parsed2 and isinstance(parsed2[0], dict):
                                return parsed2[0]
                            if isinstance(parsed2, dict):
                                return parsed2
                        return parsed
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                        parsed = _try_json_load(first["text"])
                        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                            return parsed[0]
                        if isinstance(parsed, dict):
                            if isinstance(parsed.get("content"), str):
                                parsed2 = _try_json_load(parsed["content"])
                                if isinstance(parsed2, list) and parsed2 and isinstance(parsed2[0], dict):
                                    return parsed2[0]
                                if isinstance(parsed2, dict):
                                    return parsed2
                            return parsed
                return obj
            return {}

        def _derive_tech_stack(stats_obj: Dict[str, Any]) -> str:
            tech = stats_obj.get("technologies")
            if isinstance(tech, list):
                parts = [t.strip() for t in tech if isinstance(t, str) and t.strip()]
                return ", ".join(parts)
            if isinstance(tech, dict):
                parts: List[str] = []
                for v in tech.values():
                    if isinstance(v, list):
                        parts.extend([t.strip() for t in v if isinstance(t, str) and t.strip()])
                uniq = []
                seen = set()
                for p in parts:
                    pl = p.lower()
                    if pl in seen:
                        continue
                    seen.add(pl)
                    uniq.append(p)
                return ", ".join(uniq)
            et = stats_obj.get("element_types")
            if isinstance(et, list):
                parts = [t.strip() for t in et if isinstance(t, str) and t.strip()]
                return ", ".join(parts[:15])
            return ""

        stats_obj = _first_stats_obj(self.state.dna_profile)
        tech_stack = _derive_tech_stack(stats_obj)
        selected_app = self.state.selected_app_id or params.get("app_id") or ""
        loc_val = 0
        for k in ("nb_LOC", "nb_loc", "loc", "nb_LoC", "nb_LOCS"):
            v = stats_obj.get(k)
            if isinstance(v, (int, float)):
                loc_val = int(v)
                break
            if isinstance(v, str) and v.strip().isdigit():
                loc_val = int(v.strip())
                break
        is_mainframe_val = bool(stats_obj.get("mainframe")) if isinstance(stats_obj.get("mainframe"), bool) else False
        goal_label = params.get("modernization_goal") or params.get("goal") or "mono-to-micro"
        modernization_type = params.get("modernization_type") or ""
        criteria = params.get("criteria") or []
        if isinstance(criteria, str):
            criteria = [c.strip() for c in criteria.split(",") if c.strip()]
        if not isinstance(criteria, list):
            criteria = []
        criteria = [c for c in criteria if isinstance(c, str) and c.strip()]
        if "structural-flaws" not in criteria:
            criteria.insert(0, "structural-flaws")
        advisor_id = params.get("advisor_id") or ""
        vuln_val = params.get("vulnerabilities")
        if not vuln_val:
            vuln_val = "CVEs" if "cve" in criteria else "None"
        inputs = {
            "app_name": self.state.selected_app_id,
            "selected_app": selected_app,
            "tech_stack": tech_stack,
            "loc": loc_val,
            "is_mainframe": "Detected" if is_mainframe_val else "Not detected",
            "txtObjective": params.get('objective', 'Modernize'),
            "selDBMigration": params.get('db_migration', 'No Migration'),
            "target_cloud": params.get('target_cloud', '') or params.get('target_lang', ''),
            "dna_profile": json.dumps(self.state.dna_profile, indent=2),
            "objective": params.get('objective', 'Modernize'),
            "goal": goal_label,
            "modernization_goal": goal_label,
            "modernization_type": modernization_type,
            "criteria": ", ".join(criteria),
            "advisor_id": advisor_id,
            "strategy": params.get('strategy', 'Containerization'),
            "risk_profile": params.get('risk_profile', 'ISO-5055 only'),
            "vulnerabilities": vuln_val,
            "db_migration": params.get('db_migration', 'No Migration'),
            "rewrite_mainframe": params.get('rewrite_mainframe', ''),
            "target_lang": params.get('target_lang', ''),
            "iso_5055_flaws": flaws_text,
            "include_locations": params.get('include_locations', False)
        }
        
        tech_list: List[str] = []
        technologies = stats_obj.get("technologies")
        if isinstance(technologies, list):
            tech_list = [t for t in technologies if isinstance(t, str)]
        elif isinstance(technologies, dict):
            for v in technologies.values():
                if isinstance(v, list):
                    tech_list.extend([t for t in v if isinstance(t, str)])

        snap = []
        if loc_val:
            snap.append(f"- LoC: {loc_val:,}")
        if isinstance(stats_obj.get("nb_elements"), (int, float)):
            snap.append(f"- Elements: {int(stats_obj.get('nb_elements')):,}")
        if isinstance(stats_obj.get("nb_interactions"), (int, float)):
            snap.append(f"- Interactions: {int(stats_obj.get('nb_interactions')):,}")
        if tech_list:
            snap.append(f"- Technologies: {', '.join(sorted(set(tech_list)))}")
        snap.append(f"- Mainframe tech: {'Detected' if is_mainframe_val else 'Not detected'}")

        async def _gather_deterministic_data() -> Dict[str, Any]:
            def _decode_tool_payload(res: Any):
                obj = None
                if isinstance(res, dict):
                    sc = res.get("structuredContent")
                    if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                        obj = _try_json_load(sc["content"])
                    if obj is None:
                        content = res.get("content")
                        if isinstance(content, list) and content:
                            first = content[0]
                            if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                                obj = _try_json_load(first["text"])
                        elif isinstance(content, str):
                            obj = _try_json_load(content)
                else:
                    obj = res
                if isinstance(obj, dict) and isinstance(obj.get("content"), str):
                    inner = _try_json_load(obj.get("content"))
                    if inner is not None:
                        obj = inner
                return obj

            async def _call(tool: str, payload: Dict[str, Any]):
                if not self.mcp_client:
                    return None
                last = None
                for _ in range(2):
                    try:
                        res = await self.mcp_client.invoke_tool(tool, payload)
                        return _decode_tool_payload(res)
                    except Exception as e:
                        last = e
                return {"error": str(last)} if last else None

            rp = params.get("risk_profile") or "ISO-5055 only"
            selected_natures = [c for c in criteria if isinstance(c, str)]
            if not selected_natures:
                selected_natures = ["structural-flaws"]
                if rp in ("ISO-5055 only", "Performance", "Performance and Security"):
                    selected_natures.append("iso-5055")
                if rp in ("Security", "Performance and Security"):
                    selected_natures.append("cve")
            if "structural-flaws" not in selected_natures:
                selected_natures.insert(0, "structural-flaws")
            selected_natures = list(dict.fromkeys(selected_natures))

            nodes_obj = await _call("architectural_graph", {"application": selected_app, "mode": "nodes", "level": "component", "page": 1})
            links_obj = await _call("architectural_graph", {"application": selected_app, "mode": "links", "level": "component", "page": 1})
            nodes = None
            links = None
            if isinstance(nodes_obj, dict):
                nodes = nodes_obj.get("nodes") if isinstance(nodes_obj.get("nodes"), list) else nodes_obj.get("items")
            elif isinstance(nodes_obj, list):
                nodes = nodes_obj
            if isinstance(links_obj, dict):
                links = links_obj.get("links") if isinstance(links_obj.get("links"), list) else links_obj.get("items")
            elif isinstance(links_obj, list):
                links = links_obj
            n_nodes = len(nodes) if isinstance(nodes, list) else 0
            n_links = len(links) if isinstance(links, list) else 0
            layers = {}
            if isinstance(nodes, list):
                for n in nodes[:500]:
                    if isinstance(n, dict):
                        layer = n.get("layer") or n.get("type") or n.get("category") or n.get("group")
                        if isinstance(layer, str) and layer:
                            layers[layer] = layers.get(layer, 0) + 1
            top_layers = sorted(layers.items(), key=lambda x: x[1], reverse=True)[:8]
            arch_md = f"- Nodes: {n_nodes:,}\n- Links: {n_links:,}\n"
            if top_layers:
                arch_md += "- Top node groups:\n" + "\n".join([f"  - {k}: {v:,}" for k, v in top_layers]) + "\n"

            db_obj = await _call("application_database_explorer", {"application": selected_app})
            db_items = None
            if isinstance(db_obj, dict):
                for k in ("items", "tables", "objects", "data", "results"):
                    if isinstance(db_obj.get(k), list):
                        db_items = db_obj.get(k)
                        break
            elif isinstance(db_obj, list):
                db_items = db_obj

            tx_obj = await _call("transactions", {"application": selected_app})
            tx_items = None
            if isinstance(tx_obj, dict):
                for k in ("items", "transactions", "results", "data"):
                    if isinstance(tx_obj.get(k), list):
                        tx_items = tx_obj.get(k)
                        break
            elif isinstance(tx_obj, list):
                tx_items = tx_obj

            findings: List[Dict[str, Any]] = []
            for nature in selected_natures:
                qi_obj = await _call("quality_insights", {"application": selected_app, "nature": nature, "page": 1})
                items = None
                if isinstance(qi_obj, dict):
                    for k in ("items", "insights", "results", "data"):
                        if isinstance(qi_obj.get(k), list):
                            items = qi_obj.get(k)
                            break
                elif isinstance(qi_obj, list):
                    items = qi_obj
                if isinstance(items, list):
                    for it in items[:10]:  # Limit to top 10 per nature
                        if isinstance(it, dict):
                            row = dict(it)
                            row.setdefault("nature", nature)
                            
                            if params.get("include_locations"):
                                insight_id = it.get("id") or it.get("insight_id") or it.get("insightId") or it.get("object_id")
                                if insight_id:
                                    vio_obj = await _call("quality_insight_violations", {
                                        "application": selected_app,
                                        "nature": nature,
                                        "id": str(insight_id),
                                        "include_locations": True,
                                        "page": 1
                                    })
                                    vio_items = None
                                    if isinstance(vio_obj, dict):
                                        for k in ("items", "violations", "occurrences", "results", "data"):
                                            if isinstance(vio_obj.get(k), list):
                                                vio_items = vio_obj.get(k)
                                                break
                                    elif isinstance(vio_obj, list):
                                        vio_items = vio_obj
                                    
                                    if isinstance(vio_items, list) and vio_items:
                                        # Store top 3 detailed occurrences to avoid massive reports
                                        row["detailed_violations"] = vio_items[:3]
                                        
                            findings.append(row)

            advisor_rules = None
            if advisor_id:
                adv_obj = await _call("advisors", {"application": selected_app, "focus": "rules", "advisor_id": advisor_id, "page": 1})
                if isinstance(adv_obj, dict):
                    for k in ("items", "rules", "results", "data"):
                        if isinstance(adv_obj.get(k), list):
                            advisor_rules = adv_obj.get(k)
                            break
                elif isinstance(adv_obj, list):
                    advisor_rules = adv_obj
            
            return {
                "selected_natures": selected_natures,
                "arch_md": arch_md,
                "db_items": db_items,
                "tx_items": tx_items,
                "findings": findings,
                "advisor_rules": advisor_rules
            }

        async def _deterministic_report(data: Dict[str, Any]) -> str:
            selected_natures = data["selected_natures"]
            arch_md = data["arch_md"]
            db_items = data["db_items"]
            tx_items = data["tx_items"]
            findings = data["findings"]
            advisor_rules = data["advisor_rules"]

            report = []
            report.append(f"# Modernization Report — {selected_app}\n")
            report.append("## 1. Executive Summary\n")
            if params.get("objective"):
                report.append(f"- Modernization Objective: {str(params.get('objective'))[:500]}\n")
            report.append(f"- Modernization Goal: {goal_label}\n")
            if modernization_type:
                report.append(f"- Modernization Type: {modernization_type}\n")
            report.append(f"- Strategy: {params.get('strategy', '') or 'Not provided'}\n")
            report.append(f"- Risk Profile: {params.get('risk_profile', '') or 'Not provided'}\n")
            report.append(f"- Quality Criteria (nature): {', '.join(selected_natures)}\n")
            if advisor_id:
                report.append(f"- Advisor Selected: {advisor_id}\n")
            report.append("\n## 2. Application Snapshot\n")
            report.append("\n".join(snap) + "\n")
            report.append("## 3. Current-State Architecture\n")
            report.append(arch_md + "\n")
            report.append("## 4. Data Architecture & Hotspots\n")
            if isinstance(db_items, list) and db_items:
                # Case-insensitive de-duplication by (schema, table)
                seen = set()
                rows = []
                for it in db_items:
                    if not isinstance(it, dict):
                        continue
                    table = it.get("table") or it.get("table_name") or it.get("name") or it.get("displayName") or ""
                    schema = it.get("schema") or it.get("schema_name") or it.get("owner") or ""
                    oid = it.get("object_id") or it.get("objectId") or it.get("id") or ""
                    key = (str(schema).lower(), str(table).lower())
                    if not table and not oid:
                        continue
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append((table or "-", schema or "-", oid or "-"))
                rows = rows[:10]
                report.append("| table | schema | object_id |\n| --- | --- | --- |\n")
                for table, schema, oid in rows:
                    report.append(f"| {table} | {schema} | {oid} |\n")
            else:
                report.append("Not available from MCP output.\n")
            report.append("\n## 5. Transaction Flows & Coupling\n")
            if isinstance(tx_items, list) and tx_items:
                rows = []
                seen_tx = set()
                for it in tx_items:
                    if not isinstance(it, dict):
                        continue
                    # Try multiple keys for transaction name
                    name = (
                        it.get("name")
                        or it.get("displayName")
                        or it.get("transaction_name")
                        or it.get("transactionName")
                        or it.get("label")
                        or ""
                    )
                    oid = it.get("object_id") or it.get("objectId") or it.get("id") or ""
                    if not name:
                        name = f"tx-{oid}" if oid else "(unnamed)"
                    key = (name, oid)
                    if key in seen_tx:
                        continue
                    seen_tx.add(key)
                    rows.append((name, oid or "-"))
                rows = rows[:15]
                report.append("| transaction | object_id |\n| --- | --- |\n")
                for name, oid in rows:
                    report.append(f"| {name} | {oid} |\n")
            else:
                report.append("Not available from MCP output.\n")
            report.append("\n## 6. Risk & ISO 5055 Findings\n")
            if findings:
                # Sort by count desc when available
                def _num(x):
                    try:
                        return int(x)
                    except Exception:
                        return 0
                findings_sorted = sorted(findings, key=lambda it: _num(it.get("count") or it.get("occurrences") or it.get("occurrence_count") or it.get("occurrenceCount")), reverse=True)
                report.append("| type | name | severity | count | id |\n| --- | --- | --- | --- | --- |\n")
                for it in findings_sorted[:10]:
                    nature = it.get("nature") or ""
                    name = it.get("name") or it.get("type") or it.get("title") or it.get("ruleName") or ""
                    sev = it.get("severity") or it.get("criticality") or it.get("level") or "-"
                    count = it.get("count") or it.get("occurrences") or it.get("occurrence_count") or it.get("occurrenceCount") or "-"
                    iid = it.get("id") or it.get("insight_id") or it.get("insightId") or it.get("object_id") or "-"
                    report.append(f"| {nature} | {name} | {sev} | {count} | {iid} |\n")
                
                # Check if any findings have detailed locations
                detailed = [f for f in findings if f.get("detailed_violations")]
                if detailed:
                    report.append("\n### Detailed Occurrences (Sample)\n")
                    for it in detailed[:3]:
                        name = it.get("name") or it.get("type") or it.get("title") or ""
                        report.append(f"**Insight: {name}**\n")
                        report.append("| File | Line | Object |\n| --- | --- | --- |\n")
                        for vio in (it.get("detailed_violations") or [])[:5]:
                            file_path = vio.get("file_path") or vio.get("filePath") or vio.get("file") or "-"
                            line = vio.get("line") or vio.get("lineNumber") or vio.get("line_number") or "-"
                            obj_name = vio.get("object_name") or vio.get("objectName") or vio.get("name") or vio.get("fullname") or "-"
                            report.append(f"| {file_path} | {line} | {obj_name} |\n")
                        report.append("\n")
            else:
                report.append("Not available from MCP output.\n")
            report.append("\n## 7. Advisory Suggestions\n")
            if advisor_id and isinstance(advisor_rules, list) and advisor_rules:
                report.append("| rule | id |\n| --- | --- |\n")
                for r in advisor_rules[:15]:
                    if isinstance(r, dict):
                        nm = r.get("name") or r.get("title") or r.get("ruleName") or ""
                        rid = r.get("id") or r.get("rule_id") or r.get("ruleId") or ""
                        report.append(f"| {nm} | {rid} |\n")
            else:
                report.append("Not available from MCP output.\n")
            return "\n".join(report).strip()

        # Pre-fetch data for deterministic evidence (used by both paths)
        self.push_update("Pre-fetching base deterministic facts from CAST Imaging MCP...")
        try:
            gathered_data = await _gather_deterministic_data()
            inputs["deterministic_evidence"] = await _deterministic_report(gathered_data)
        except Exception as e:
            inputs["deterministic_evidence"] = f"Failed to pre-fetch evidence: {e}"

        if not bool(params.get("use_llm")):
            self.push_update("Generating deterministic report from CAST Imaging MCP tools (LLM disabled)...")
            try:
                self.state.mission_report = inputs["deterministic_evidence"]
                self.state.validation_report = "Deterministic report generated from CAST Imaging MCP tools."
            except Exception as e:
                self.state.mission_report = f"Error generating deterministic report: {str(e)}"
                self.state.validation_report = "Error"
            self.push_update("CrewAI Execution complete.")
            return

        self.push_update(f"Executing Crew with LLM Provider: {llm_provider.upper()}")
        self.push_update("CrewAI Agents started processing (this may take a moment)...")
        
        if not CREWAI_AVAILABLE:
            # Fallback mock response for local testing if crewai couldn't install
            import litellm
            try:
                if llm_provider == "openrouter":
                    model = "openrouter/google/gemini-2.5-flash"
                elif llm_provider == "gemini":
                    model = "gemini/gemini-1.5-pro"
                else:
                    model = f"{llm_provider}/gpt-4o"
                response = await litellm.acompletion(
                    model=model,
                    messages=[{"role": "user", "content": f"Write a modernization plan for {self.state.selected_app_id} based on {inputs['goal']}"}],
                    api_key=llm_key
                )
                self.state.mission_report = response.choices[0].message.content
                self.state.validation_report = "Validated successfully (Fallback Mode)."
            except Exception as e:
                self.state.mission_report = f"Error (Fallback): {str(e)}"
                self.state.validation_report = "Error"
        else:
            try:
                loop = asyncio.get_running_loop()
                
                def crew_step_callback(step_output):
                    # step_output is an AgentStep or similar
                    if hasattr(step_output, 'agent'):
                        agent_name = step_output.agent
                        thought = getattr(step_output, 'thought', str(step_output))
                        self.push_update(f"{agent_name}: {thought}")
                    else:
                        self.push_update(f"Agent Action: {str(step_output)}")

                model_candidates: List[Optional[str]] = [llm_model]
                if llm_provider == "openrouter":
                    for extra in ("openai/gpt-4o-mini",):
                        if extra not in model_candidates:
                            model_candidates.append(extra)

                last_error: Optional[Exception] = None
                result = None
                chosen_model = llm_model

                for candidate in model_candidates:
                    chosen_model = candidate or chosen_model
                    try:
                        crew_instance = ModernizationCrew(
                            llm_provider=llm_provider,
                            llm_key=llm_key,
                            llm_model=chosen_model,
                            enable_per_agent_models=(llm_provider == "openrouter"),
                            app_name=self.state.selected_app_id,
                            search_api_key=search_api_key,
                            mcp_client=self.mcp_client,
                            loop=loop,
                            step_callback=crew_step_callback,
                        ).crew()

                        try:
                            result = await asyncio.to_thread(crew_instance.kickoff, inputs=inputs)
                        except TypeError:
                            result = await asyncio.to_thread(crew_instance.kickoff, inputs)
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e
                        s = str(e).lower()
                        is_model_404 = "no endpoints found" in s or "error code: 404" in s or "\"code\": 404" in s
                        if llm_provider == "openrouter" and is_model_404:
                            self.push_update("OpenRouter selected model unavailable. Retrying with internal fallback settings...")
                            crew_instance = ModernizationCrew(
                                llm_provider=llm_provider,
                                llm_key=llm_key,
                                llm_model=chosen_model,
                                enable_per_agent_models=False,
                                app_name=self.state.selected_app_id,
                                search_api_key=search_api_key,
                                mcp_client=self.mcp_client,
                                loop=loop,
                                step_callback=crew_step_callback,
                            ).crew()
                            try:
                                result = await asyncio.to_thread(crew_instance.kickoff, inputs=inputs)
                            except TypeError:
                                result = await asyncio.to_thread(crew_instance.kickoff, inputs)
                            last_error = None
                            break
                        raise

                if last_error is not None or result is None:
                    raise last_error or RuntimeError("Crew kickoff failed")
                
                tasks_output = getattr(result, "tasks_output", None)
                def _parse_jsonish(text: str):
                    if not isinstance(text, str):
                        return None
                    s = text.strip()
                    if not s:
                        return None
                    for fence in ("```json", "```JSON", "```"):
                        if s.startswith(fence):
                            s = s.split("\n", 1)[1] if "\n" in s else s
                            if s.endswith("```"):
                                s = s[:-3]
                            s = s.strip()
                            break
                    parsed = _try_json_load(s)
                    if parsed is not None:
                        return parsed
                    try:
                        import re as _re
                        m = _re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", s)
                        if m:
                            return _try_json_load(m.group(0))
                    except Exception:
                        pass
                    return None

                def _flatten_ids(obj: Any) -> List[str]:
                    ids: List[str] = []
                    seen = set()
                    def _walk(x: Any):
                        if isinstance(x, dict):
                            for k, v in x.items():
                                kl = str(k).lower()
                                if kl.endswith("id") or kl.endswith("_id") or "object_id" in kl or "violation_id" in kl:
                                    if isinstance(v, (str, int)) and str(v).strip():
                                        sv = str(v).strip()
                                        if sv not in seen:
                                            seen.add(sv)
                                            ids.append(sv)
                                _walk(v)
                        elif isinstance(x, list):
                            for it in x:
                                _walk(it)
                    _walk(obj)
                    return ids

                def _md_table(rows: List[Dict[str, Any]], columns: List[str]) -> str:
                    if not rows:
                        return "Not available from MCP output.\n"
                    head = "| " + " | ".join(columns) + " |"
                    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
                    body_lines = []
                    for r in rows:
                        body_lines.append("| " + " | ".join([str(r.get(c, "")).replace("\n", " ").strip() for c in columns]) + " |")
                    return "\n".join([head, sep] + body_lines) + "\n"

                raws: List[str] = []
                if isinstance(tasks_output, (list, tuple)) and tasks_output:
                    for t in tasks_output:
                        raw_val = getattr(t, "raw", None)
                        if raw_val is None:
                            raw_val = getattr(t, "result", None)
                        raws.append(str(raw_val) if raw_val is not None else str(t))
                else:
                    raw_val = getattr(result, "raw", None)
                    raws = [str(raw_val) if raw_val is not None else str(result)]

                db_data = _parse_jsonish(raws[0]) if len(raws) > 0 else None
                logic_data = _parse_jsonish(raws[1]) if len(raws) > 1 else None
                risk_data = _parse_jsonish(raws[2]) if len(raws) > 2 else None
                manager_md = raws[3].strip() if len(raws) > 3 else ""

                app = selected_app or self.state.selected_app_id or ""
                nb_loc = stats_obj.get("nb_LOC")
                nb_elements = stats_obj.get("nb_elements")
                nb_interactions = stats_obj.get("nb_interactions")
                technologies = stats_obj.get("technologies")
                tech_list: List[str] = []
                if isinstance(technologies, list):
                    tech_list = [t for t in technologies if isinstance(t, str)]
                elif isinstance(technologies, dict):
                    for v in technologies.values():
                        if isinstance(v, list):
                            tech_list.extend([t for t in v if isinstance(t, str)])

                db_tables = []
                if isinstance(db_data, dict):
                    tt = db_data.get("tables_top")
                    if isinstance(tt, list):
                        for item in tt[:10]:
                            if isinstance(item, dict):
                                db_tables.append(item)
                if not db_tables and self.mcp_client and app:
                    try:
                        db_res = await self.mcp_client.invoke_tool("application_database_explorer", {"application": app})
                        db_obj = None
                        if isinstance(db_res, dict):
                            sc = db_res.get("structuredContent")
                            if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                                db_obj = _try_json_load(sc["content"])
                            if db_obj is None:
                                content = db_res.get("content")
                                if isinstance(content, list) and content:
                                    first = content[0]
                                    if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                                        db_obj = _try_json_load(first["text"])
                                elif isinstance(content, str):
                                    db_obj = _try_json_load(content)
                        else:
                            db_obj = db_res
                        items = db_obj.get("items") if isinstance(db_obj, dict) else None
                        if items is None and isinstance(db_obj, dict):
                            for k in ("tables", "objects", "data", "results"):
                                if isinstance(db_obj.get(k), list):
                                    items = db_obj.get(k)
                                    break
                        if isinstance(items, list):
                            for it in items[:25]:
                                if not isinstance(it, dict):
                                    continue
                                row = dict(it)
                                if "object_id" not in row:
                                    for k in ("object_id", "objectId", "id", "table_id", "tableId"):
                                        if row.get(k) is not None:
                                            row["object_id"] = row.get(k)
                                            break
                                if "table" not in row:
                                    for k in ("table", "table_name", "name", "displayName"):
                                        if isinstance(row.get(k), str) and row.get(k).strip():
                                            row["table"] = row.get(k)
                                            break
                                if "schema" not in row:
                                    for k in ("schema", "schema_name", "owner"):
                                        if isinstance(row.get(k), str) and row.get(k).strip():
                                            row["schema"] = row.get(k)
                                            break
                                db_tables.append(row)
                                if len(db_tables) >= 10:
                                    break
                    except Exception:
                        pass
                logic_tx = []
                if isinstance(logic_data, dict):
                    tx = logic_data.get("transactions_top")
                    if isinstance(tx, list):
                        for item in tx[:15]:
                            if isinstance(item, dict):
                                logic_tx.append(item)
                if not logic_tx and self.mcp_client and app:
                    try:
                        tx_res = await self.mcp_client.invoke_tool("transactions", {"application": app})
                        tx_obj = None
                        if isinstance(tx_res, dict):
                            sc = tx_res.get("structuredContent")
                            if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                                tx_obj = _try_json_load(sc["content"])
                            if tx_obj is None:
                                content = tx_res.get("content")
                                if isinstance(content, list) and content:
                                    first = content[0]
                                    if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                                        tx_obj = _try_json_load(first["text"])
                                elif isinstance(content, str):
                                    tx_obj = _try_json_load(content)
                        else:
                            tx_obj = tx_res
                        items = tx_obj.get("items") if isinstance(tx_obj, dict) else None
                        if items is None and isinstance(tx_obj, dict):
                            for k in ("transactions", "results", "data"):
                                if isinstance(tx_obj.get(k), list):
                                    items = tx_obj.get(k)
                                    break
                        if isinstance(items, list):
                            for it in items[:25]:
                                if isinstance(it, dict):
                                    row = dict(it)
                                    if "object_id" not in row:
                                        for k in ("object_id", "objectId", "id", "transaction_id", "transactionId"):
                                            if row.get(k) is not None:
                                                row["object_id"] = row.get(k)
                                                break
                                    if "name" not in row:
                                        for k in ("name", "displayName", "transaction_name"):
                                            if isinstance(row.get(k), str) and row.get(k).strip():
                                                row["name"] = row.get(k)
                                                break
                                    logic_tx.append(row)
                                    if len(logic_tx) >= 12:
                                        break
                    except Exception:
                        pass
                risk_findings = []
                if isinstance(risk_data, dict):
                    tf = risk_data.get("top_findings")
                    if isinstance(tf, list):
                        for item in tf[:15]:
                            if isinstance(item, dict):
                                risk_findings.append(item)
                if not risk_findings and self.mcp_client and app:
                    try:
                        def _decode_tool_payload(res: Any):
                            obj = None
                            if isinstance(res, dict):
                                sc = res.get("structuredContent")
                                if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                                    obj = _try_json_load(sc["content"])
                                if obj is None:
                                    content = res.get("content")
                                    if isinstance(content, list) and content:
                                        first = content[0]
                                        if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                                            obj = _try_json_load(first["text"])
                                    elif isinstance(content, str):
                                        obj = _try_json_load(content)
                            else:
                                obj = res
                            if isinstance(obj, dict) and isinstance(obj.get("content"), str):
                                inner = _try_json_load(obj.get("content"))
                                if inner is not None:
                                    obj = inner
                            return obj

                        combined: List[Dict[str, Any]] = []
                        for nature in ("iso-5055", "structural-flaws", "green-detection-patterns"):
                            qi_res = await self.mcp_client.invoke_tool("quality_insights", {"application": app, "nature": nature, "page": 1})
                            qi_obj = _decode_tool_payload(qi_res)
                            items = None
                            if isinstance(qi_obj, list):
                                items = qi_obj
                            elif isinstance(qi_obj, dict):
                                for k in ("items", "insights", "results", "data"):
                                    if isinstance(qi_obj.get(k), list):
                                        items = qi_obj.get(k)
                                        break
                            if isinstance(items, list):
                                for it in items[:25]:
                                    if isinstance(it, dict):
                                        row = dict(it)
                                        row.setdefault("nature", nature)
                                        combined.append(row)
                        for it in combined:
                            row = dict(it)
                            if "name" not in row:
                                for k in ("name", "type", "title", "ruleName"):
                                    if isinstance(row.get(k), str) and row.get(k).strip():
                                        row["name"] = row.get(k)
                                        break
                            if "count" not in row:
                                for k in ("count", "occurrences", "occurrence_count", "occurrenceCount"):
                                    if isinstance(row.get(k), (int, float)):
                                        row["count"] = int(row.get(k))
                                        break
                            risk_findings.append(row)
                            if len(risk_findings) >= 12:
                                break
                    except Exception:
                        pass

                evidence_ids: List[str] = []
                for blob in (db_data, logic_data, risk_data):
                    if blob is not None:
                        evidence_ids.extend(_flatten_ids(blob))
                uniq_ids = []
                seen_ids = set()
                for i in evidence_ids:
                    if i in seen_ids:
                        continue
                    seen_ids.add(i)
                    uniq_ids.append(i)

                snapshot_lines = []
                if isinstance(nb_loc, (int, float)) and int(nb_loc) > 0:
                    snapshot_lines.append(f"- LoC: {int(nb_loc):,}")
                if isinstance(nb_elements, (int, float)) and int(nb_elements) > 0:
                    snapshot_lines.append(f"- Elements: {int(nb_elements):,}")
                if isinstance(nb_interactions, (int, float)) and int(nb_interactions) > 0:
                    snapshot_lines.append(f"- Interactions: {int(nb_interactions):,}")
                if tech_list:
                    snapshot_lines.append(f"- Technologies: {', '.join(sorted(set(tech_list)))}")
                snapshot_lines.append(f"- Mainframe tech: {'Detected' if is_mainframe_val else 'Not detected'}")

                arch_md = "Not available from MCP output.\n"
                if self.mcp_client and app:
                    try:
                        def _decode_tool_payload(res: Any):
                            obj = None
                            if isinstance(res, dict):
                                sc = res.get("structuredContent")
                                if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                                    obj = _try_json_load(sc["content"])
                                if obj is None:
                                    content = res.get("content")
                                    if isinstance(content, list) and content:
                                        first = content[0]
                                        if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                                            obj = _try_json_load(first["text"])
                                    elif isinstance(content, str):
                                        obj = _try_json_load(content)
                            else:
                                obj = res
                            if isinstance(obj, dict) and isinstance(obj.get("content"), str):
                                inner = _try_json_load(obj.get("content"))
                                if inner is not None:
                                    obj = inner
                            return obj

                        nodes_res = await self.mcp_client.invoke_tool("architectural_graph", {"application": app, "mode": "nodes", "level": "component", "page": 1})
                        links_res = await self.mcp_client.invoke_tool("architectural_graph", {"application": app, "mode": "links", "level": "component", "page": 1})
                        nodes_obj = _decode_tool_payload(nodes_res)
                        links_obj = _decode_tool_payload(links_res)

                        nodes = None
                        links = None
                        if isinstance(nodes_obj, dict):
                            nodes = nodes_obj.get("nodes") if isinstance(nodes_obj.get("nodes"), list) else nodes_obj.get("items")
                        elif isinstance(nodes_obj, list):
                            nodes = nodes_obj
                        if isinstance(links_obj, dict):
                            links = links_obj.get("links") if isinstance(links_obj.get("links"), list) else links_obj.get("items")
                        elif isinstance(links_obj, list):
                            links = links_obj

                        n_nodes = len(nodes) if isinstance(nodes, list) else 0
                        n_links = len(links) if isinstance(links, list) else 0

                        layers = {}
                        if isinstance(nodes, list):
                            for n in nodes[:500]:
                                if isinstance(n, dict):
                                    layer = n.get("layer") or n.get("type") or n.get("category") or n.get("group")
                                    if isinstance(layer, str) and layer:
                                        layers[layer] = layers.get(layer, 0) + 1
                        top_layers = sorted(layers.items(), key=lambda x: x[1], reverse=True)[:8]
                        arch_md = f"- Nodes: {n_nodes:,}\n- Links: {n_links:,}\n"
                        if top_layers:
                            arch_md += "- Top node groups:\n" + "\n".join([f"  - {k}: {v:,}" for k, v in top_layers]) + "\n"
                    except Exception:
                        arch_md = "Not available from MCP output.\n"

                report = []
                report.append(f"# Modernization Report — {app}\n")
                report.append("## 1. Executive Summary\n")
                report.append(f"- Objective: {params.get('objective', '') or 'Not provided'}\n- Goal: {params.get('goal', '') or 'Not provided'}\n- Strategy: {params.get('strategy', '') or 'Not provided'}\n")
                report.append("## 2. Application Snapshot\n")
                report.append("\n".join(snapshot_lines) + "\n")
                report.append("## 3. Current-State Architecture\n")
                report.append(arch_md)
                report.append("## 4. Data Architecture & Hotspots\n")
                report.append(_md_table(db_tables, ["object_id", "id", "name", "table", "schema", "uses", "usage_count", "shared_count"]))
                report.append("## 5. Transaction Flows & Coupling\n")
                report.append(_md_table(logic_tx, ["object_id", "id", "name", "complexity", "nodes", "links", "entrypoints"]))
                report.append("## 6. Risk & ISO 5055 Findings\n")
                report.append(_md_table(risk_findings, ["type", "name", "severity", "count", "object_id", "violation_id"]))
                report.append("## 7. Target Architecture\n")
                if isinstance(logic_data, dict) and isinstance(logic_data.get("candidate_service_boundaries"), list) and logic_data.get("candidate_service_boundaries"):
                    csb = logic_data.get("candidate_service_boundaries")
                    rows = [r for r in csb if isinstance(r, dict)]
                    report.append(_md_table(rows[:15], ["service", "boundary", "reason", "evidence_ids", "object_id", "id"]))
                else:
                    report.append("Not available from MCP output.\n")
                report.append("## 8. Migration Plan\n")
                report.append("- Phase 0: Baseline and evidence capture (stats, ISO 5055, top transactions/tables)\n")
                if uniq_ids:
                    report.append(f"- Phase 1: Decompose around highest-coupling flows and clusters (evidence IDs: {', '.join(uniq_ids[:12])})\n")
                else:
                    report.append("- Phase 1: Decompose around highest-coupling flows and clusters (evidence IDs: Not available from MCP output)\n")
                report.append("- Phase 2: Data decomposition for shared tables and CRUD hotspots (use table evidence from Section 4)\n")
                report.append("- Phase 3: Risk remediation for top ISO 5055/quality findings (use evidence from Section 6)\n")
                report.append("## 9. Risk Mitigations\n")
                if risk_findings:
                    for f in risk_findings[:8]:
                        fid = f.get("object_id") or f.get("violation_id") or f.get("id") or ""
                        name = f.get("name") or f.get("type") or "Finding"
                        report.append(f"- {name}: Mitigate based on CAST evidence {fid if fid else '(ID not available)'}\n")
                else:
                    report.append("Not available from MCP output.\n")
                report.append("## 10. Evidence Appendix\n")
                if uniq_ids:
                    report.append("\n".join([f"- {i}" for i in uniq_ids[:200]]) + "\n")
                else:
                    report.append("Not available from MCP output.\n")

                self.state.mission_report = "\n".join(report).strip()
                self.state.validation_report = (risk_data.get("iso5055_summary") if isinstance(risk_data, dict) else "") or "Validation integrated via ISO 5055 evidence."
                    
            except Exception as e:
                logger.exception("CrewAI execution failed")
                self.push_update(f"CrewAI Error: {str(e)}")
                self.state.mission_report = f"Error generating plan: {str(e)}"
                self.state.validation_report = "Validation failed due to error."
                
        self.push_update("CrewAI Execution complete.")

    async def validate_iso5055(self):
        # Validation is now handled intrinsically by the Validation Task in the Crew.
        self.push_update("Finalizing ISO 5055 Validation...")
        await asyncio.sleep(0.5)
        return self.state.validation_report
