from typing import Any, Dict, List, Optional
from crewai import Agent, Task, Crew
from .handler import _flatten_tool_result, _extract_error_message, _looks_like_app_item

# Agents
PortfolioAgent = Agent(
    role="Portfolio Agent",
    goal="List available applications from MCP in normalized JSON [{id,name}]",
    backstory="Calls MCP tools and normalizes output; filters out validation echoes.",
    tools=[],
    allow_delegation=False,
)

ProfileAgent = Agent(
    role="Profile Agent",
    goal="Fetch Application Technical Profile via MCP stats and normalize fields, infer mainframe",
    backstory="Reads stats tool and produces canonical profile fields.",
    tools=[],
    allow_delegation=False,
)

ManagerAgent = Agent(
    role="Manager Agent",
    goal="Orchestrate specialists and produce consolidated Markdown + JSON sections",
    backstory="Delegates to specialists and merges final result for UI.",
    tools=[],
    allow_delegation=True,
)

ArchitectureAgent = Agent(
    role="Architecture Specialist",
    goal="Blueprint and boundary notes based on trajectory",
    tools=[],
    allow_delegation=False,
)

DataSovereigntyAgent = Agent(
    role="Data Specialist",
    goal="DB decomposition and data strategy plan",
    tools=[],
    allow_delegation=False,
)

PlatformAgent = Agent(
    role="Platform Specialist",
    goal="Containerization/Kubernetes/PaaS plan based on ambition",
    tools=[],
    allow_delegation=False,
)

CloudStrategyAgent = Agent(
    role="Cloud Specialist",
    goal="Pattern-driven cloud service mapping",
    tools=[],
    allow_delegation=False,
)

MainframeRewriteAgent = Agent(
    role="Mainframe Rewrite Specialist",
    goal="Rewrite plan (target language, batch handling, depth)",
    tools=[],
    allow_delegation=False,
)


def _infer_mainframe(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False
    if bool(obj.get("mainframe")):
        return True
    platforms = obj.get("platforms")
    if isinstance(platforms, dict) and bool(platforms.get("mainframe")):
        return True
    keywords = {
        "mainframe", "cobol", "jcl", "cics", "ims", "db2", "vsam", "z/os", "zos",
        "pl/i", "pli", "pl1", "natural", "adabas", "rpg", "as/400", "as400", "ibm i", "ibm z"
    }
    for k in ("technologies", "element_types"):
        v = obj.get(k)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    s = item.strip().lower()
                    if any(kw in s for kw in keywords):
                        return True
    tech = obj.get("technologies")
    if isinstance(tech, dict):
        langs = tech.get("languages")
        if isinstance(langs, list):
            for item in langs:
                if isinstance(item, str):
                    s = item.strip().lower()
                    if any(kw in s for kw in keywords):
                        return True
    return False


def run_list_apps(mcp_client) -> List[Dict[str, str]]:
    # Crew wrapper (semantic) — execution delegates to MCP client for reliability
    crew = Crew(agents=[PortfolioAgent], tasks=[Task(description="List applications", agent=PortfolioAgent)])
    _ = crew.kickoff()
    res_primary = mcp_client.invoke_tool("applications", {})
    apps_primary = _flatten_tool_result(res_primary)
    if apps_primary:
        err = _extract_error_message(apps_primary)
        if err and not any(_looks_like_app_item(x) for x in apps_primary):
            raise RuntimeError(err)
        norm: List[Dict[str, str]] = []
        for a in apps_primary:
            if isinstance(a, dict):
                aid = a.get("id") or a.get("application_id") or a.get("applicationId")
                aname = a.get("name") or a.get("application_name") or a.get("applicationName") or a.get("displayName")
                if aname and not aid:
                    aid = aname
                if aid or aname:
                    norm.append({"id": aid or "", "name": aname or str(aid or "")})
            elif isinstance(a, str):
                norm.append({"id": a, "name": a})
        return norm
    return []


def run_profile(mcp_client, app_id: str) -> Dict[str, Any]:
    crew = Crew(agents=[ProfileAgent], tasks=[Task(description=f"Profile {app_id}", agent=ProfileAgent)])
    _ = crew.kickoff()
    res = mcp_client.invoke_tool("stats", {"app_id": app_id})
    flat = _flatten_tool_result(res)
    err = _extract_error_message(flat if flat else res)
    if err and not any(_looks_like_app_item(x) for x in flat):
        raise RuntimeError(err)
    # Heuristic: prefer dict payloads; if list, take first dict-like
    data = None
    if isinstance(res, dict):
        data = res
    elif isinstance(res, list) and res:
        first = res[0]
        if isinstance(first, dict):
            data = first
    if not isinstance(data, dict):
        data = {}
    inferred = _infer_mainframe(data)
    platforms = data.get("platforms") or {}
    if not isinstance(platforms, dict):
        platforms = {}
    platforms.setdefault("mainframe", inferred)
    data["platforms"] = platforms
    data.setdefault("mainframe", inferred)
    return data


def run_mission(profile: Dict[str, Any], mission: Dict[str, Any]) -> Dict[str, Any]:
    # Create specialist tasks (semantic) but merge deterministically here
    tasks = [
        Task(description=f"Architecture trajectory={mission.get('trajectory')}", agent=ArchitectureAgent),
        Task(description=f"Data sovereignty={mission.get('data_sov')}", agent=DataSovereigntyAgent),
        Task(description=f"Platform ambition={mission.get('ambition')}", agent=PlatformAgent),
        Task(description=f"Cloud pattern={mission.get('pattern')} target={mission.get('target_cloud')}", agent=CloudStrategyAgent),
    ]
    if bool(mission.get("rewrite_mainframe")):
        tasks.append(Task(description=f"Mainframe rewrite target={mission.get('target_lang')} batch={mission.get('batch_handling')} depth={mission.get('extraction_depth')}", agent=MainframeRewriteAgent))
    crew = Crew(
        agents=[ManagerAgent, ArchitectureAgent, DataSovereigntyAgent, PlatformAgent, CloudStrategyAgent, MainframeRewriteAgent],
        tasks=tasks
    )
    _ = crew.kickoff()
    app_name = (profile.get("name") or profile.get("app_id") or mission.get("name") or "").strip()
    tech = ", ".join(profile.get("technologies") or []) if isinstance(profile.get("technologies"), list) else str(profile.get("technologies") or "")
    loc = profile.get("nb_LOC") or profile.get("nb_LOC_value") or profile.get("loc") or 0
    try:
        loc_int = int(loc)
    except Exception:
        loc_int = 0
    pattern = mission.get("pattern") or ""
    target_cloud = mission.get("target_cloud") or ""
    rewrite_flag = bool(mission.get("rewrite_mainframe"))
    summary = f"# Modernization Mission for {app_name}\n\n- Tech Stack: {tech}\n- LOC: {loc_int:,}\n- Pattern: {pattern}\n" + (f"- Target Cloud: {target_cloud}\n" if target_cloud else "") + (f"- Rewrite Mainframe: {'Yes' if rewrite_flag else 'No'}\n")
    arch = f"## Architecture Insights\n\n- Trajectory: {mission.get('trajectory') or 'N/A'}\n- Recommended boundary mapping and service identification aligned with mission.\n"
    data_plan = f"## Data Strategy\n\n- Strategy: {mission.get('data_sov') or 'N/A'}\n- DB decomposition and migration steps.\n"
    platform = f"## Platform Modernization\n\n- Ambition: {mission.get('ambition') or 'N/A'}\n- Containerization/Kubernetes/PaaS recommendations.\n"
    cloud = f"## Cloud Transformation\n\n- Pattern: {pattern}\n- Target: {target_cloud or 'N/A'}\n- Native service mapping aligned with mission.\n"
    mf = ""
    if rewrite_flag:
        mf = f"## Mainframe Rewrite Plan\n\n- Target Language: {mission.get('target_lang') or 'N/A'}\n- Batch Handling: {mission.get('batch_handling') or 'N/A'}\n- Extraction Depth: {mission.get('extraction_depth') or 'N/A'}\n"
    roadmap = "## Modernization Roadmap\n\n1. Baseline profile\n2. Boundary discovery\n3. Data alignment\n4. Platform modernization\n5. Cloud migration sequence\n"
    report_md = "\n\n".join([summary, arch, data_plan, platform, cloud, mf, roadmap]).strip()
    return {
        "executive_summary": summary,
        "architecture_insights": "\n\n".join([arch, data_plan, platform, cloud]).strip(),
        "modernization_roadmap": roadmap,
        "report_md": report_md,
    }
