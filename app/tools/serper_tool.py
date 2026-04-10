import os
import json
import logging
from typing import Optional, Any
try:
    from crewai.tools import BaseTool
except Exception:
    from crewai.tools.tool_usage import BaseTool
import httpx

logger = logging.getLogger("archaion.serper")

class SerperSearchTool(BaseTool):
    name: str = "serper_search"
    description: str = "Google Search via Serper.dev for cloud pricing/service references. Use concise queries."

    api_key: Optional[str] = None

    def _run(self, query: str, **kwargs: Any) -> str:
        key = self.api_key or os.getenv("SERPER_API_KEY", "")
        if not key:
            return "Serper API key not configured."
        try:
            headers = {"X-API-KEY": key, "Content-Type": "application/json"}
            payload = {"q": query, "num": 5, "gl": "us"}
            with httpx.Client(timeout=10) as client:
                r = client.post("https://google.serper.dev/search", headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                # Extract top titles/links succinctly
                items = []
                for res in data.get("organic", [])[:5]:
                    items.append({"title": res.get("title"), "link": res.get("link")})
                return json.dumps(items, indent=2)
        except Exception as e:
            logger.warning(f"Serper error: {e!r}")
            return f"Serper error: {e}"

    async def _arun(self, query: str, **kwargs: Any) -> str:
        return self._run(query, **kwargs)

