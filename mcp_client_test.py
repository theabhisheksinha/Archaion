import asyncio
import json
import os
import sys
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
import httpx
from contextlib import AsyncExitStack

def _iter_exception_group(exc: BaseException):
    if hasattr(exc, "exceptions") and isinstance(getattr(exc, "exceptions"), (list, tuple)):
        for e in getattr(exc, "exceptions"):
            yield from _iter_exception_group(e)
    else:
        yield exc

def _is_http_status_error_400(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response is not None and exc.response.status_code == 400
        except Exception:
            return False
    return False

def _summarize_http_status_error(exc: httpx.HTTPStatusError) -> str:
    url = ""
    status = ""
    body = ""
    try:
        url = str(exc.request.url) if exc.request else ""
    except Exception:
        url = ""
    try:
        status = str(exc.response.status_code) if exc.response else ""
    except Exception:
        status = ""
    try:
        body = (exc.response.text or "") if exc.response else ""
    except Exception:
        body = ""
    body = body.strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 300:
        body = body[:300] + "…"
    return f"HTTP {status} for {url} body={body}"

async def _try_jsonrpc_fallback(url: str, http_client: httpx.AsyncClient):
    base = url.rstrip("/")
    candidates = [base]
    if base.endswith("/mcp"):
        candidates.append(base + "/")
    elif base.endswith("/mcp/"):
        candidates.append(base[:-1])

    session_id = None
    last_error = None
    for cand in candidates:
        for method in ("session/open", "session/create"):
            try:
                resp = await http_client.post(
                    cand,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": {}},
                )
                resp.raise_for_status()
                data = resp.json()
                session_id = (data.get("result") or {}).get("sessionId")
                if session_id:
                    return cand, session_id
            except httpx.HTTPStatusError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

    if last_error:
        raise last_error
    raise RuntimeError("Unable to establish MCP JSON-RPC session")

async def _jsonrpc_tools_call(url: str, http_client: httpx.AsyncClient, session_id: str, tool_name: str, arguments: dict):
    resp = await http_client.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"sessionId": session_id, "name": tool_name, "arguments": arguments or {}},
        },
    )
    resp.raise_for_status()
    return resp.json()

async def test_mcp_connection(server_name):
    # 1. Load your workspace mcp.json
    with open("mcp.json", "r") as f:
        config = json.load(f)
    
    servers = config.get("servers", {})
    server_data = servers.get(server_name)
    if not server_data:
        available = ", ".join(servers.keys()) or "(none)"
        print(f"Error: Server '{server_name}' not found in mcp.json. Available: {available}")
        return

    # Normalize keys (url vs httpUrl) and headers
    url = server_data.get("url") or server_data.get("httpUrl")
    headers = server_data.get("headers", {})
    if "x-api-key" in headers and "X-API-KEY" not in headers:
        headers = {**headers, "X-API-KEY": headers["x-api-key"]}

    print(f"--- Connecting to {server_name} at {url} ---")

    try:
        async with AsyncExitStack() as stack:
            http_client = await stack.enter_async_context(httpx.AsyncClient(headers=headers, follow_redirects=True))
            read, write, _ = await stack.enter_async_context(streamable_http_client(url, http_client=http_client))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # 4. List Tools to verify connection success
            tools = await session.list_tools()
            print(f"Successfully connected! Discovered {len(tools.tools)} tools.")
            for tool in tools.tools:
                print(f" - Found Tool: {tool.name}")

            # 5. List Prompts
            prompts = await session.list_prompts()
            print(f"Discovered {len(prompts.prompts)} prompts.")
            for prompt in prompts.prompts:
                print(f" - Found Prompt: {prompt.name}")

            # 6. List Resources (with pagination)
            all_resources = []
            cursor = None
            while True:
                params = types.PaginatedRequestParams(cursor=cursor, limit=100)
                result = await session.list_resources(params=params)
                all_resources.extend(result.resources)
                cursor = result.nextCursor
                if not cursor:
                    break

            print(f"Discovered {len(all_resources)} resources.")
            for res in all_resources:
                uri = getattr(res, "uri", None) or getattr(res, "id", None) or "unknown"
                print(f" - Found Resource: {uri}")

            # 7. List applications via tool and fetch stats
            def _extract_json_contents(result):
                items = []
                for c in getattr(result, "content", []) or []:
                    t = getattr(c, "type", None)
                    if t == "json":
                        v = getattr(c, "json", None) or getattr(c, "data", None)
                        items.append(v)
                    elif t == "text":
                        text = getattr(c, "text", "") or ""
                        try:
                            items.append(json.loads(text))
                        except Exception:
                            items.append(text)
                return items

            apps_result = await session.call_tool("applications", {})
            apps_payloads = _extract_json_contents(apps_result)
            apps_list = []
            for p in apps_payloads:
                if isinstance(p, list):
                    apps_list.extend(p)
                elif isinstance(p, dict):
                    if "applications" in p and isinstance(p["applications"], list):
                        apps_list.extend(p["applications"])
                    elif "items" in p and isinstance(p["items"], list):
                        apps_list.extend(p["items"])
                    elif "content" in p and isinstance(p["content"], str):
                        added = False
                        s = p["content"]
                        try:
                            decoded = json.loads(s)
                            if isinstance(decoded, str):
                                decoded = json.loads(decoded)
                            if isinstance(decoded, list):
                                apps_list.extend(decoded)
                                added = True
                        except Exception:
                            pass
                        if not added:
                            i0 = s.find("[")
                            i1 = s.rfind("]")
                            if i0 != -1 and i1 != -1 and i1 > i0:
                                try:
                                    decoded = json.loads(s[i0 : i1 + 1])
                                    if isinstance(decoded, str):
                                        decoded = json.loads(decoded)
                                    if isinstance(decoded, list):
                                        apps_list.extend(decoded)
                                        added = True
                                except Exception:
                                    pass
                        if not added:
                            try:
                                s_dec = bytes(s, "utf-8").decode("unicode_escape")
                                i0 = s_dec.find("[")
                                i1 = s_dec.rfind("]")
                                if i0 != -1 and i1 != -1 and i1 > i0:
                                    decoded = json.loads(s_dec[i0 : i1 + 1])
                                    if isinstance(decoded, list):
                                        apps_list.extend(decoded)
                                        added = True
                            except Exception:
                                pass
                        if not added:
                            import re
                            names = re.findall(r'"name"\\s*:\\s*"([^"]+)"', s)
                            disp = re.findall(r'"displayName"\\s*:\\s*"([^"]+)"', s)
                            for idx, n in enumerate(names):
                                dn = disp[idx] if idx < len(disp) else n
                                apps_list.append({"name": n, "displayName": dn})

            print(f"Applications: {len(apps_list)}")
            for app in apps_list:
                app_id = None
                app_name = None
                if isinstance(app, dict):
                    app_id = app.get("id") or app.get("application_id") or app.get("applicationId")
                    app_name = app.get("name") or app.get("application_name") or app.get("applicationName")
                print(f" - {app_name or 'unknown'} ({app_id or 'unknown'})")
            if not apps_list:
                print("Applications tool returned no structured items; raw content:")
                for c in getattr(apps_result, "content", []) or []:
                    t = getattr(c, "type", None)
                    if t == "json":
                        v = getattr(c, "json", None) or getattr(c, "data", None)
                        print(json.dumps(v, ensure_ascii=False))
                    elif t == "text":
                        print(getattr(c, "text", "") or "")

        stats_tool = next((t for t in tools.tools if t.name == "stats"), None)
        stats_param = "application_id"
        if stats_tool and getattr(stats_tool, "inputSchema", None):
            schema = stats_tool.inputSchema or {}
            props = {}
            if isinstance(schema, dict):
                props = schema.get("properties") or {}
                req = schema.get("required") or []
                if isinstance(req, list) and req:
                    stats_param = req[0]
                elif isinstance(props, dict) and props:
                    for k in props.keys():
                        if "app" in k.lower() and "id" in k.lower():
                            stats_param = k
                            break
                    if stats_param == "application_id":
                        for k in props.keys():
                            if k.lower() in ("application", "name", "applicationname", "application_name"):
                                stats_param = k
                                break

        for app in apps_list:
            app_id = None
            app_name = None
            if isinstance(app, dict):
                app_id = app.get("id") or app.get("application_id") or app.get("applicationId")
                app_name = app.get("name") or app.get("application_name") or app.get("applicationName")
            value = app_id if ("id" in stats_param.lower()) else app_name
            if not value:
                continue
            stats_result = await session.call_tool("stats", {stats_param: value})
            stats_payloads = _extract_json_contents(stats_result)
            stats_data = None
            for p in stats_payloads:
                if isinstance(p, dict):
                    stats_data = p
                    break
            parsed_summary = None
            if isinstance(stats_data, dict) and isinstance(stats_data.get("content"), str):
                s = stats_data["content"]
                try:
                    decoded = json.loads(s)
                    if isinstance(decoded, str):
                        decoded = json.loads(decoded)
                    if isinstance(decoded, list) and decoded:
                        d0 = decoded[0] if isinstance(decoded[0], dict) else None
                        if d0:
                            parsed_summary = {
                                "name": d0.get("name"),
                                "nb_elements": d0.get("nb_elements"),
                                "nb_interactions": d0.get("nb_interactions"),
                                "nb_LOC": d0.get("nb_LOC"),
                                "technologies": d0.get("technologies"),
                            }
                except Exception:
                    pass
                if parsed_summary is None:
                    try:
                        s_dec = bytes(s, "utf-8").decode("unicode_escape")
                        i0 = s_dec.find("[")
                        i1 = s_dec.rfind("]")
                        if i0 != -1 and i1 != -1 and i1 > i0:
                            decoded = json.loads(s_dec[i0 : i1 + 1])
                            if isinstance(decoded, list) and decoded:
                                d0 = decoded[0] if isinstance(decoded[0], dict) else None
                                if d0:
                                    parsed_summary = {
                                        "name": d0.get("name"),
                                        "nb_elements": d0.get("nb_elements"),
                                        "nb_interactions": d0.get("nb_interactions"),
                                        "nb_LOC": d0.get("nb_LOC"),
                                        "technologies": d0.get("technologies"),
                                    }
                    except Exception:
                        pass
            summary = parsed_summary if parsed_summary is not None else (stats_data if stats_data is not None else stats_payloads)
            print(f"Stats for {app_name or app_id}: {json.dumps(summary, ensure_ascii=False)}")
    except Exception as e:
        flattened = list(_iter_exception_group(e))
        status_errors = [x for x in flattened if isinstance(x, httpx.HTTPStatusError)]
        if status_errors:
            for se in status_errors:
                print(_summarize_http_status_error(se))
        else:
            print(f"Connection failed: {e}")

        if any(_is_http_status_error_400(x) for x in flattened):
            print("StreamableHTTP path returned 400. Trying JSON-RPC fallback…")
            rpc_headers = {**headers, "Accept": "application/json", "Content-Type": "application/json"}
            async with httpx.AsyncClient(headers=rpc_headers, follow_redirects=True) as http_client:
                rpc_url, sid = await _try_jsonrpc_fallback(url, http_client)
                print(f"JSON-RPC session established at {rpc_url} sessionId={sid}")
                apps_json = await _jsonrpc_tools_call(
                    rpc_url,
                    http_client,
                    sid,
                    "applications",
                    {"page": 1, "meta": {}},
                )
                print("JSON-RPC tools/call applications raw response:")
                print(json.dumps(apps_json, ensure_ascii=False))
                return
        raise

if __name__ == "__main__":
    # Test your 'imaging_express' environment first
    default = "imaging"
    choice = sys.argv[1] if len(sys.argv) > 1 else default
    asyncio.run(test_mcp_connection(choice))
