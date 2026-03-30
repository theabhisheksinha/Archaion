import os
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
try:
    from crew import run_analysis
except Exception:
    run_analysis = None

class MCPClient:
    def __init__(self, base_url: str, api_key: str, protocol: str = "rest", tool_map: Optional[Dict[str, str]] = None, extra_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.protocol = (protocol or "rest").lower()
        self.tool_map = tool_map or {}
        self.session_id: Optional[str] = None
        headers = {
            "X-API-KEY": api_key,
            "x-api-key": api_key,
            "imaging_api_key": api_key,
            "Accept": "application/json, text/event-stream",
        }
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    async def _open_session(self) -> None:
        if self.protocol != "jsonrpc" or self.session_id:
            return
        # Try SSE session endpoint first
        sse_paths = [f"{self.base_url}/session", self.base_url if self.base_url.endswith("/session") else None]
        for sp in sse_paths:
            if not sp:
                continue
            try:
                resp = await self._client.get(sp, headers={"Accept": "text/event-stream"})
                resp.raise_for_status()
                txt = resp.text or ""
                sid = None
                if "sessionId" in txt:
                    try:
                        import re
                        m = re.search(r'"sessionId"\s*:\s*"([^"]+)"', txt)
                        if m:
                            sid = m.group(1)
                    except Exception:
                        pass
                if not sid:
                    try:
                        data = json.loads(txt)
                        sid = (data.get("result") or {}).get("sessionId")
                    except Exception:
                        pass
                if sid:
                    self.session_id = sid
                    logger.info("MCP SSE session established")
                    return
            except httpx.HTTPStatusError as e:
                body = ""
                try:
                    body = e.response.text
                except Exception:
                    pass
                logger.warning(f"MCP SSE session status={e.response.status_code if e.response else 'n/a'} body={body[:200]}")
            except Exception as ex:
                logger.exception(f"MCP SSE session error {ex}")
        # Try session/open then session/create
        for method in ("session/open", "session/create"):
            try:
                resp = await self._client.post(
                    self.base_url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": {}},
                )
                resp.raise_for_status()
                data = resp.json()
                sid = (data.get("result") or {}).get("sessionId")
                if sid:
                    self.session_id = sid
                    return
            except httpx.HTTPStatusError as e:
                body = ""
                try:
                    body = e.response.text
                except Exception:
                    pass
                logger.warning(f"MCP session method {method} status={e.response.status_code if e.response else 'n/a'} body={body[:200]}")
                continue
            except Exception as ex:
                logger.exception(f"MCP session error {method} {ex}")
                continue
        # If still no session, raise to surface upstream config issue
        raise HTTPException(status_code=400, detail="MCP session handshake failed")

    async def invoke_tool(self, tool: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if self.protocol == "jsonrpc":
                await self._open_session()
                url = self.base_url
                # Try primary and synonyms
                primary = self.tool_map.get(tool, tool)
                synonyms = []
                if tool in ("list_applications", "applications"):
                    synonyms = [primary, "applications", "mcp_imaging_linux_applications", "list_applications"]
                elif tool in ("statistics", "stats"):
                    synonyms = [primary, "stats", "statistics"]
                else:
                    synonyms = [primary]
                last_error = None
                for name in synonyms:
                    for attempt in range(2):
                        body = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {
                                "sessionId": self.session_id,
                                "name": name,
                                "arguments": payload or {},
                            },
                        }
                        try:
                            resp = await self._client.post(url, json=body)
                            resp.raise_for_status()
                            logger.info(f"MCP tools/call {name} ok")
                            data = resp.json()
                            return (data.get("result") or data)
                        except httpx.HTTPStatusError as e:
                            last_error = e
                            body_txt = ""
                            status_code = None
                            try:
                                status_code = e.response.status_code if e.response else None
                                body_txt = e.response.text if e.response else ""
                            except Exception:
                                body_txt = ""
                            logger.warning(
                                f"MCP tools/call {name} status={status_code if status_code is not None else 'n/a'} body={body_txt[:200]}"
                            )
                            body_l = (body_txt or "").lower()
                            looks_like_invalid_session = (
                                status_code in (400, 404)
                                and "session" in body_l
                                and any(x in body_l for x in ("invalid", "expired", "not found", "unknown"))
                            )
                            if attempt == 0 and looks_like_invalid_session:
                                self.session_id = None
                                await self._open_session()
                                continue
                            break
                # If all jsonrpc attempts fail, try REST fallback for known tools
                if tool in ("list_applications", "applications", "statistics"):
                    rest_paths = [
                        f"{self.base_url}/tools/{primary}",
                        f"{self.base_url}/tools/{tool}",
                    ]
                    for p in rest_paths:
                        try:
                            resp = await self._client.post(p, json=payload or {})
                            resp.raise_for_status()
                            logger.info(f"MCP REST {p} ok")
                            return resp.json()
                        except httpx.HTTPStatusError as e:
                            logger.warning(f"MCP REST {p} status={e.response.status_code if e.response else 'n/a'}")
                            continue
                # All attempts failed
                if last_error:
                    raise last_error
            else:
                url = f"{self.base_url}/tools/{tool}"
                resp = await self._client.post(url, json=payload or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else 500
            body_txt = ""
            try:
                body_txt = e.response.text if e.response is not None else ""
            except Exception:
                body_txt = ""
            detail = "Tool invocation failed"
            if body_txt:
                detail = f"{detail}: {body_txt[:400]}"
            raise HTTPException(status_code=status, detail=detail)
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Upstream service unreachable")

class MCPStreamAdapter:
    def __init__(self, base_url: str, headers: Dict[str, str]):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self._stack: Optional[AsyncExitStack] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._read = None
        self._write = None
        self.session: Optional[ClientSession] = None

    async def open(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        if "Accept" not in self.headers:
            self.headers["Accept"] = "application/json, text/event-stream"
        self._http = await self._stack.enter_async_context(httpx.AsyncClient(headers=self.headers, follow_redirects=True))
        self._read, self._write, _ = await self._stack.enter_async_context(streamable_http_client(self.base_url, http_client=self._http))
        self.session = await self._stack.enter_async_context(ClientSession(self._read, self._write))
        await self.session.initialize()

    async def aclose(self):
        try:
            if self._stack:
                await self._stack.__aexit__(None, None, None)
        except Exception:
            pass

    async def invoke_tool(self, tool: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.session:
            raise HTTPException(status_code=500, detail="MCP stream session not initialized")
        name = tool
        # Name adjustments similar to JSON-RPC path
        if tool in ("list_applications", "applications"):
            for cand in ["applications", "mcp_imaging_linux_applications", "list_applications", tool]:
                try:
                    result = await self.session.call_tool(cand, payload or {})
                    extracted = _extract_stream_payload(result)
                    flat = _flatten_tool_result(extracted)
                    err = _extract_error_message(flat if flat else extracted)
                    if err and not any(_looks_like_app_item(x) for x in flat):
                        continue
                    if flat and _is_error_only_list(flat):
                        continue
                    return extracted
                except Exception:
                    continue
            raise HTTPException(status_code=502, detail="Tool invocation failed")
        elif tool in ("statistics", "stats"):
            for cand in ["stats", "statistics", tool]:
                try:
                    result = await self.session.call_tool(cand, payload or {})
                    extracted = _extract_stream_payload(result)
                    flat = _flatten_tool_result(extracted)
                    err = _extract_error_message(flat if flat else extracted)
                    if err and not any(_looks_like_app_item(x) for x in flat):
                        continue
                    if flat and _is_error_only_list(flat):
                        continue
                    return extracted
                except Exception:
                    continue
            raise HTTPException(status_code=502, detail="Tool invocation failed")
        else:
            result = await self.session.call_tool(name, payload or {})
            return _extract_stream_payload(result)

def _extract_stream_payload(result) -> Dict[str, Any]:
    items = []
    try:
        content = getattr(result, "content", []) or []
    except Exception:
        content = []
    for c in content:
        t = getattr(c, "type", None)
        if t == "json":
            v = getattr(c, "json", None) or getattr(c, "data", None)
            items.append(v)
        elif t == "text":
            text = getattr(c, "text", "") or ""
            # Try multiple decoding strategies
            decoded = None
            try:
                decoded = json.loads(text)
                if isinstance(decoded, str):
                    decoded = json.loads(decoded)
            except Exception:
                pass
            if isinstance(decoded, list) or isinstance(decoded, dict):
                items.append(decoded)
            else:
                # Fallback: unicode-escape and bracket slice
                try:
                    s_dec = bytes(text, "utf-8").decode("unicode_escape")
                    i0 = s_dec.find("[")
                    i1 = s_dec.rfind("]")
                    if i0 != -1 and i1 != -1 and i1 > i0:
                        decoded = json.loads(s_dec[i0 : i1 + 1])
                        items.append(decoded)
                    else:
                        items.append(text)
                except Exception:
                    items.append(text)
    # normalize applications lists
    for p in items:
        if isinstance(p, list):
            return p
        if isinstance(p, dict):
            if "applications" in p and isinstance(p["applications"], list):
                return p["applications"]
            if "items" in p and isinstance(p["items"], list):
                return p["items"]
            if "content" in p and isinstance(p["content"], str):
                s0 = p["content"]
                candidates = [s0]
                try:
                    candidates.append(bytes(s0, "utf-8").decode("unicode_escape"))
                except Exception:
                    pass
                for s in candidates:
                    try:
                        decoded = json.loads(s)
                        if isinstance(decoded, str):
                            decoded = json.loads(decoded)
                        if isinstance(decoded, list):
                            return decoded
                        if isinstance(decoded, dict):
                            if isinstance(decoded.get("applications"), list):
                                return decoded["applications"]
                            if isinstance(decoded.get("items"), list):
                                return decoded["items"]
                    except Exception:
                        try:
                            i0 = s.find("[")
                            i1 = s.rfind("]")
                            if i0 != -1 and i1 != -1 and i1 > i0:
                                decoded = json.loads(s[i0 : i1 + 1])
                                if isinstance(decoded, list):
                                    return decoded
                        except Exception:
                            pass
    # regex fallback to extract names
    try:
        import re
        merged = " ".join(x if isinstance(x, str) else json.dumps(x) for x in items)
        names = re.findall(r'"name"\s*:\s*"([^"]+)"', merged)
        disp = re.findall(r'"displayName"\s*:\s*"([^"]+)"', merged)
        if names:
            out = []
            for idx, n in enumerate(names):
                dn = disp[idx] if idx < len(disp) else n
                out.append({"name": n, "displayName": dn})
            return out
    except Exception:
        pass
    return {"items": items}

    async def aclose(self) -> None:
        await self._client.aclose()

def _normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    h = dict(headers or {})
    if "x-api-key" in h and "X-API-KEY" not in h:
        h["X-API-KEY"] = h["x-api-key"]
    if "X-API-KEY" in h and "x-api-key" not in h:
        h["x-api-key"] = h["X-API-KEY"]
    if "imaging_api_key" not in h:
        if "x-api-key" in h:
            h["imaging_api_key"] = h["x-api-key"]
        elif "X-API-KEY" in h:
            h["imaging_api_key"] = h["X-API-KEY"]
    return h

def _extract_content_payloads(content) -> list[Any]:
    out: list[Any] = []
    for c in content or []:
        if isinstance(c, dict):
            t = c.get("type")
            if t == "json":
                out.append(c.get("json") if "json" in c else c.get("data"))
            elif t == "text":
                out.append(c.get("text", "") or "")
        else:
            t = getattr(c, "type", None)
            if t == "json":
                out.append(getattr(c, "json", None) or getattr(c, "data", None))
            elif t == "text":
                out.append(getattr(c, "text", "") or "")
    return out

def _flatten_tool_result(res: Any) -> list[Any]:
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        if isinstance(res.get("applications"), list):
            return res["applications"]
        if isinstance(res.get("items"), list):
            return res["items"]
        content = res.get("content")
        if isinstance(content, list):
            payloads = _extract_content_payloads(content)
            flattened: list[Any] = []
            for p in payloads:
                decoded = p
                if isinstance(decoded, str):
                    try:
                        decoded = json.loads(decoded)
                        if isinstance(decoded, str):
                            decoded = json.loads(decoded)
                    except Exception:
                        decoded = p
                if isinstance(decoded, list):
                    flattened.extend(decoded)
                elif isinstance(decoded, dict):
                    if isinstance(decoded.get("applications"), list):
                        flattened.extend(decoded["applications"])
                    elif isinstance(decoded.get("items"), list):
                        flattened.extend(decoded["items"])
                    else:
                        flattened.append(decoded)
                else:
                    flattened.append(decoded)
            return flattened
        if isinstance(content, str):
            try:
                decoded = json.loads(content)
                if isinstance(decoded, str):
                    decoded = json.loads(decoded)
                if isinstance(decoded, list):
                    return decoded
                if isinstance(decoded, dict) and isinstance(decoded.get("applications"), list):
                    return decoded["applications"]
                if isinstance(decoded, dict) and isinstance(decoded.get("items"), list):
                    return decoded["items"]
            except Exception:
                return []
    return []

def _extract_error_message(res: Any) -> Optional[str]:
    if isinstance(res, dict):
        err = res.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()
        items = res.get("items")
        if isinstance(items, list) and items:
            return _extract_error_message(items)
    if isinstance(res, list) and res:
        for x in res:
            if isinstance(x, str):
                s = x.strip()
                sl = s.lower()
                if s and ("unknown tool" in sl or "validation error" in sl or "unexpected keyword argument" in sl or "unable to fetch applications" in sl):
                    return s
            if isinstance(x, dict):
                err = x.get("error")
                if isinstance(err, str) and err.strip():
                    return err.strip()
    if isinstance(res, str):
        s = res.strip()
        sl = s.lower()
        if s and ("unknown tool" in sl or "validation error" in sl or "unexpected keyword argument" in sl or "unable to fetch applications" in sl):
            return s
    return None

def _looks_like_error_text(s: str) -> bool:
    sl = (s or "").strip().lower()
    return bool(sl) and ("unknown tool" in sl or "validation error" in sl or "unexpected keyword argument" in sl or "unable to fetch applications" in sl)

def _looks_like_app_item(x: Any) -> bool:
    if isinstance(x, str):
        s = x.strip()
        return bool(s) and not _looks_like_error_text(s)
    if isinstance(x, dict):
        for k in ("id", "application_id", "applicationId", "name", "application_name", "applicationName", "displayName"):
            v = x.get(k)
            if isinstance(v, str) and v.strip():
                return True
            if v is not None and k in ("id", "application_id", "applicationId"):
                return True
    return False

def _is_error_only_list(items: list[Any]) -> bool:
    if not items:
        return False
    if all(isinstance(x, dict) and "error" in x and len(x.keys()) == 1 for x in items):
        return True
    if all(isinstance(x, str) and _looks_like_error_text(x) for x in items):
        return True
    return False


class AnalyzeRequest(BaseModel):
    app_id: str
    cloud_strategy: str


load_dotenv()
def _get_env(name: str):
    val = os.getenv(name)
    if val:
        return val
    here = os.path.dirname(__file__)
    env_path = os.path.abspath(os.path.join(here, "..", "..", "..", ".env"))
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if ":" in s and "=" not in s:
                    k, v = s.split(":", 1)
                elif "=" in s:
                    k, v = s.split("=", 1)
                else:
                    continue
                if k.strip() == name:
                    return v.strip()
    except Exception:
        pass
    return None

CAST_MCP_URL = _get_env("CAST_MCP_URL") or ""
CAST_X_API_KEY = _get_env("CAST_X_API_KEY") or ""
_offline_raw = _get_env("MCP_OFFLINE") or ""
MCP_OFFLINE = _offline_raw.strip().lower() in {"1", "true", "yes"}
_proto = (_get_env("MCP_PROTOCOL") or "rest").lower()
_tool_list = _get_env("MCP_TOOL_LIST_APPS") or "applications"
_tool_stats = _get_env("MCP_TOOL_STATISTICS") or "stats"
_tool_map = {"list_applications": _tool_list, "applications": _tool_list, "statistics": _tool_stats, "stats": _tool_stats}
_tenant = _get_env("CAST_TENANT")
if _tenant and _tenant.strip().lower() in {"default", "none", "null"}:
    _tenant = None
_auto_offline_raw = _get_env("MCP_AUTO_OFFLINE_ON_FAILURE") or ""
AUTO_OFFLINE_ON_FAILURE = _auto_offline_raw.strip().lower() in {"1", "true", "yes"}
_strategies_raw = _get_env("CLOUD_STRATEGIES") or ""
try:
    _strategies_cfg = json.loads(_strategies_raw) if _strategies_raw else None
except Exception:
    _strategies_cfg = None
_default_strategies = [
    {"value": "aws_lift_shift", "label": "AWS · Lift-and-Shift"},
    {"value": "aws_replatform", "label": "AWS · Replatform"},
    {"value": "azure_lift_shift", "label": "Azure · Lift-and-Shift"},
    {"value": "azure_replatform", "label": "Azure · Replatform"},
    {"value": "gcp_refactor", "label": "GCP · Refactor"},
]
_extra_headers_raw = _get_env("MCP_EXTRA_HEADERS") or ""
try:
    _extra_headers_cfg = json.loads(_extra_headers_raw) if _extra_headers_raw else None
except Exception:
    _extra_headers_cfg = None

 

def _setup_logger():
    lvl = (_get_env("LOG_LEVEL") or "INFO").upper()
    log_file = _get_env("LOG_FILE")
    logger = logging.getLogger("archaion")
    logger.setLevel(getattr(logging, lvl, logging.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.handlers = []
    logger.addHandler(sh)
    if log_file:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            pass
    return logger

logger = _setup_logger()
def _load_mcp_json_candidates(api_key: str) -> list[tuple[str, Dict[str, str]]]:
    here = os.path.dirname(__file__)
    paths = []
    paths.append(os.path.abspath(os.path.join(here, "..", "..", "..", "mcp.json")))
    paths.append(os.path.abspath(os.path.join(here, "..", "..", "..", "..", "mcp.json")))
    paths.append(os.path.abspath(os.path.join(here, "..", "..", "..", "..", "archaion", "mcp.json")))
    paths.append(os.path.abspath(os.path.join(here, "..", "..", "..", "..", "Archaion", "mcp.json")))
    candidates: list[tuple[str, Dict[str, str]]] = []
    for cfg_path in paths:
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            servers = cfg.get("servers") or {}
            for _, srv in servers.items():
                url = str(srv.get("url") or srv.get("httpUrl") or "").strip()
                if not url:
                    continue
                headers = {}
                h = srv.get("headers") or {}
                for k, v in h.items():
                    s = str(v)
                    if "${input:imaging-key}" in s:
                        s = api_key
                    headers[str(k)] = s
                candidates.append((url.rstrip("/"), headers))
            for key in ("Imaging-Linux", "imaging_express"):
                block = cfg.get(key) or {}
                srv = block.get("imaging") or block
                url = str(srv.get("url") or srv.get("httpUrl") or "").strip().strip(" `")
                if url:
                    headers = {}
                    h = srv.get("headers") or {}
                    for k, v in h.items():
                        headers[str(k)] = str(v)
                    candidates.append((url.rstrip("/"), headers))
        except Exception:
            continue
    return candidates


@asynccontextmanager
async def lifespan(app: FastAPI):
    candidates = [(CAST_MCP_URL.rstrip("/"), {"x-user-tenant": _tenant} if _tenant else {})]
    for url, hdrs in _load_mcp_json_candidates(CAST_X_API_KEY):
        if hdrs and "x-user-tenant" not in hdrs and _tenant:
            hdrs["x-user-tenant"] = _tenant
        candidates.append((url, hdrs))
    seen = set()
    unique_candidates = []
    for url, hdrs in candidates:
        key = (url, json.dumps(hdrs or {}, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append((url, hdrs))
    candidates = unique_candidates
    fallback_api_key = CAST_X_API_KEY
    if not fallback_api_key:
        for _, hdrs in candidates:
            if not hdrs:
                continue
            k = hdrs.get("x-api-key") or hdrs.get("X-API-KEY") or hdrs.get("imaging_api_key")
            if isinstance(k, str) and k.strip():
                fallback_api_key = k.strip()
                break
    chosen = None
    for url, hdrs in candidates:
        try:
            logger.info(f"MCP connect attempt {url}")
            merged_hdrs = {}
            merged_hdrs.update(hdrs or {})
            if isinstance(_extra_headers_cfg, dict):
                merged_hdrs.update(_extra_headers_cfg)
            merged_hdrs = _normalize_headers(merged_hdrs)
            header_variants = [merged_hdrs]
            if merged_hdrs.get("x-user-tenant"):
                no_tenant = dict(merged_hdrs)
                no_tenant.pop("x-user-tenant", None)
                header_variants.append(no_tenant)
            # Prefer streamable transport first
            try:
                for hv in header_variants:
                    stream_client = MCPStreamAdapter(url, hv)
                    await stream_client.open()
                    logger.info(f"MCP stream connected {url}")
                    try:
                        await stream_client.invoke_tool("applications", {})
                        chosen = stream_client
                        break
                    except Exception as se2:
                        await stream_client.aclose()
                        logger.warning(f"MCP stream validation failed {url} {se2}")
                if chosen:
                    break
            except Exception as se:
                logger.warning(f"MCP stream connect failed {url} {se}")
                for hv in header_variants:
                    api_key_effective = fallback_api_key or CAST_X_API_KEY
                    client = MCPClient(url, api_key_effective, "jsonrpc", _tool_map, hv)
                    await client._open_session()
                    logger.info(f"MCP jsonrpc connected {url}")
                    try:
                        sample = await client.invoke_tool("applications", {})
                        flat = _flatten_tool_result(sample)
                        if flat and not _is_error_only_list(flat) and any(_looks_like_app_item(x) for x in flat):
                            chosen = client
                            break
                        await client.aclose()
                        logger.warning(f"MCP jsonrpc {url} has empty applications; trying next candidate")
                    except Exception as ve2:
                        await client.aclose()
                        logger.warning(f"MCP jsonrpc validation failed {url} {ve2}")
                if chosen:
                    break
        except HTTPException:
            logger.warning(f"MCP handshake failed at {url}")
            continue
        except Exception:
            logger.exception(f"MCP connect error at {url}")
            continue
    if not chosen and AUTO_OFFLINE_ON_FAILURE:
        globals()["MCP_OFFLINE"] = True
        logger.warning("MCP offline fallback enabled")
    mcp = chosen or MCPClient(CAST_MCP_URL, fallback_api_key or CAST_X_API_KEY, "jsonrpc", _tool_map, {"x-user-tenant": _tenant} if _tenant else {})
    app.state.mcp = mcp
    try:
        yield
    finally:
        try:
            await mcp.aclose()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    rid = str(uuid.uuid4())
    start = time.time()
    logger.info(f"req {rid} {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        dur = int((time.time() - start) * 1000)
        logger.info(f"res {rid} {response.status_code} {dur}ms")
        return response
    except Exception as e:
        dur = int((time.time() - start) * 1000)
        logger.exception(f"err {rid} {request.method} {request.url.path} {dur}ms {e}")
        raise

def _http_exc_handler(request, exc: HTTPException):
    logger.warning(f"http_exc {request.url.path} {exc.status_code} {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

def _generic_exc_handler(request, exc: Exception):
    logger.exception(f"unhandled_exc {request.url.path} {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

app.add_exception_handler(HTTPException, _http_exc_handler)
app.add_exception_handler(Exception, _generic_exc_handler)

@app.get("/health")
def health():
    logger.info("health")
    return {"status": "ok"}

@app.get("/applications")
async def applications():
    if MCP_OFFLINE:
        logger.info("applications offline")
        return [
            {"id": "WebGoat_v3", "name": "WebGoat v3"},
            {"id": "HRMGMT_COB", "name": "HR Management COBOL"},
        ]
    try:
        res_primary = await app.state.mcp.invoke_tool("applications", {})
        apps_primary = _flatten_tool_result(res_primary)
        if apps_primary:
            err = _extract_error_message(apps_primary)
            if err and not any(_looks_like_app_item(x) for x in apps_primary):
                raise HTTPException(status_code=502, detail=err)
            norm = []
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
            logger.info(f"applications live {len(norm)}")
            return norm
        # Paginated fetch: aggregate pages until empty or limit reached
        apps: list = []
        for page in range(1, 11):
            args = {"page": page, "meta": {}}
            res = await app.state.mcp.invoke_tool("list_applications", args)
            page_items: list = []
            if isinstance(res, list):
                page_items = res
            elif isinstance(res, dict):
                if isinstance(res.get("applications"), list):
                    page_items = res["applications"]
                elif isinstance(res.get("items"), list):
                    page_items = res["items"]
                elif isinstance(res.get("content"), str):
                    s = res["content"]
                    try:
                        decoded = json.loads(s)
                        if isinstance(decoded, str):
                            decoded = json.loads(decoded)
                        if isinstance(decoded, list):
                            page_items = decoded
                    except Exception:
                        pass
            # Filter out validation error echoes
            if page_items and all(isinstance(x, str) for x in page_items):
                txt = " ".join(page_items)
                if "validation error" in txt and "Unexpected keyword argument" in txt:
                    page_items = []
            if not page_items:
                if page == 1:
                    # Retry without arguments for gateways that ignore paging params
                    res0 = await app.state.mcp.invoke_tool("list_applications")
                    if isinstance(res0, list):
                        page_items = res0
                    elif isinstance(res0, dict):
                        if isinstance(res0.get("applications"), list):
                            page_items = res0["applications"]
                        elif isinstance(res0.get("items"), list):
                            page_items = res0["items"]
                if not page_items:
                    break
            apps.extend(page_items)
        # Normalize shape to {id,name}
        norm = []
        for a in apps:
            if isinstance(a, dict):
                aid = a.get("id") or a.get("application_id") or a.get("applicationId")
                aname = a.get("name") or a.get("application_name") or a.get("applicationName") or a.get("displayName")
                if aname and not aid:
                    aid = aname
                if aid or aname:
                    norm.append({"id": aid or "", "name": aname or str(aid or "")})
            elif isinstance(a, str):
                norm.append({"id": a, "name": a})
        logger.info(f"applications live {len(norm)}")
        return norm
    except HTTPException as e:
        logger.warning(f"applications error {e.status_code} {e.detail}")
        raise

@app.get("/mcp/tools")
async def mcp_tools():
    mcp = getattr(app.state, "mcp", None)
    try:
        # Stream adapter exposes session; JSON-RPC path does not
        sess = getattr(mcp, "session", None)
        if sess:
            tools = await sess.list_tools()
            names = [getattr(t, "name", "") for t in (tools.tools or [])]
            return {"tools": names}
        return {"tools": []}
    except Exception as e:
        logger.exception(f"mcp_tools error {e}")
        raise HTTPException(status_code=500, detail="Failed to list tools")

@app.get("/strategies")
def strategies():
    items = _strategies_cfg if isinstance(_strategies_cfg, list) else _default_strategies
    logger.info(f"strategies {len(items)}")
    return {"items": items}

@app.get("/mcp/status")
def mcp_status():
    mcp = getattr(app.state, "mcp", None)
    ok_stream = bool(getattr(mcp, "session", None))
    ok_rpc = bool(getattr(mcp, "session_id", None))
    ok = not MCP_OFFLINE and mcp and (ok_stream or ok_rpc)
    return {
        "connected": ok,
        "offline": MCP_OFFLINE,
        "endpoint": (CAST_MCP_URL or "").strip(),
        "protocol": _proto,
        "tenant": _tenant or "",
    }

@app.get("/dna")
async def dna(app_id: str = Query(..., description="Application identifier")):
    if MCP_OFFLINE:
        logger.info(f"dna offline {app_id}")
        if app_id == "WebGoat_v3":
            return {
                "app_id": "WebGoat_v3",
                "technologies": {"languages": ["Java"], "frameworks": ["Spring"]},
                "platforms": {"mainframe": False},
            }
        if app_id == "HRMGMT_COB":
            return {
                "app_id": "HRMGMT_COB",
                "mainframe": True,
                "technologies": {"languages": ["COBOL", "JCL"]},
                "platforms": {"mainframe": True},
            }
        return {"app_id": app_id, "technologies": {"languages": []}}
    try:
        def _coerce_int(v: Any) -> Optional[int]:
            if v is None:
                return None
            if isinstance(v, bool):
                return None
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, str):
                s = v.strip()
                if not s or s.lower() in {"n/a", "na", "none", "null"}:
                    return None
                digits = "".join(ch for ch in s if ch.isdigit())
                if digits:
                    try:
                        return int(digits)
                    except Exception:
                        return None
            return None

        def _infer_mainframe(obj: Any) -> bool:
            if not isinstance(obj, dict):
                return False
            if bool(obj.get("mainframe")):
                return True
            platforms = obj.get("platforms")
            if isinstance(platforms, dict) and bool(platforms.get("mainframe")):
                return True
            keywords = {
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

        def _normalize_stats_payload(obj: Any) -> Any:
            if isinstance(obj, list):
                return [_normalize_stats_payload(x) for x in obj]
            if not isinstance(obj, dict):
                return obj
            loc_val = _coerce_int(obj.get("nb_LOC") if "nb_LOC" in obj else obj.get("nb_loc") if "nb_loc" in obj else obj.get("loc"))
            if "nb_LOC_value" not in obj:
                obj["nb_LOC_value"] = loc_val
            inferred = _infer_mainframe(obj)
            if "mainframe" not in obj:
                obj["mainframe"] = inferred
            platforms = obj.get("platforms")
            if not isinstance(platforms, dict):
                platforms = {}
                obj["platforms"] = platforms
            if "mainframe" not in platforms:
                platforms["mainframe"] = inferred
            return obj

        params_to_try = [
            ("application", app_id),
            ("application_id", app_id),
            ("app_id", app_id),
            ("name", app_id),
            ("applicationName", app_id),
        ]

        def _decode_stats(res: Any) -> Optional[Any]:
            if isinstance(res, dict) and isinstance(res.get("content"), str):
                s = res["content"]
                candidates = [s]
                try:
                    candidates.append(bytes(s, "utf-8").decode("unicode_escape"))
                except Exception:
                    pass
                for cand in candidates:
                    try:
                        decoded = json.loads(cand)
                        if isinstance(decoded, str):
                            decoded = json.loads(decoded)
                        if isinstance(decoded, list) and decoded:
                            return decoded[0]
                    except Exception:
                        try:
                            i0 = cand.find("[")
                            i1 = cand.rfind("]")
                            if i0 != -1 and i1 != -1 and i1 > i0:
                                decoded = json.loads(cand[i0 : i1 + 1])
                                if isinstance(decoded, list) and decoded:
                                    return decoded[0]
                        except Exception:
                            pass
            return None

        last: Any = None
        stream_exc: Optional[Exception] = None
        for k, v in params_to_try:
            try:
                res = await app.state.mcp.invoke_tool("stats", {k: v})
            except Exception as e:
                stream_exc = e
                break
            last = res
            flat = _flatten_tool_result(res)
            err = _extract_error_message(flat if flat else res)
            if err and not any(_looks_like_app_item(x) for x in flat):
                continue
            decoded = _decode_stats(res)
            if decoded is not None:
                logger.info(f"dna live {app_id}")
                return _normalize_stats_payload(decoded)
            logger.info(f"dna live {app_id}")
            return _normalize_stats_payload(res)

        mcp_obj = getattr(app.state, "mcp", None)
        base_url = getattr(mcp_obj, "base_url", None) or CAST_MCP_URL
        hdrs = getattr(mcp_obj, "headers", None) or {}
        api_key = hdrs.get("x-api-key") or hdrs.get("X-API-KEY") or hdrs.get("imaging_api_key") or CAST_X_API_KEY
        rpc_client = MCPClient(str(base_url).rstrip("/"), str(api_key or ""), "jsonrpc", _tool_map, _normalize_headers(hdrs))
        try:
            for k, v in params_to_try:
                res = await rpc_client.invoke_tool("stats", {k: v})
                last = res
                flat = _flatten_tool_result(res)
                err = _extract_error_message(flat if flat else res)
                if err and not any(_looks_like_app_item(x) for x in flat):
                    continue
                decoded = _decode_stats(res)
                if decoded is not None:
                    logger.info(f"dna live {app_id}")
                    return _normalize_stats_payload(decoded)
                logger.info(f"dna live {app_id}")
                return _normalize_stats_payload(res)
        finally:
            try:
                await rpc_client.aclose()
            except Exception:
                pass

        if stream_exc:
            raise stream_exc
        logger.info(f"dna live {app_id}")
        return _normalize_stats_payload(last) if last is not None else {"app_id": app_id}
    except HTTPException as e:
        logger.warning(f"dna error {app_id} {e.status_code} {e.detail}")
        raise

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        logger.info(f"analyze start {req.app_id} {req.cloud_strategy}")
        global run_analysis
        if run_analysis is None:
            from crew import run_analysis as _ra
            run_analysis = _ra
        res = await run_analysis(req.app_id, req.cloud_strategy, app.state.mcp)
        logger.info(f"analyze done {req.app_id}")
        return res
    except Exception as e:
        logger.exception(f"analyze error {req.app_id} {e}")
        raise

def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"status":"ok"}',
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
