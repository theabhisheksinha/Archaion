import os
import json
import logging
from typing import Optional, Any
try:
    from crewai.tools import BaseTool
except Exception:
    from crewai.tools.tool_usage import BaseTool
import httpx

logger = logging.getLogger("archaion.searchapi")

class SearchApiTool(BaseTool):
    name: str = "searchapi_google_search"
    description: str = "Google Search via searchapi.io for cloud service/pricing references. Use concise queries."

    api_key: Optional[str] = None

    def _run(self, query: str, **kwargs: Any) -> str:
        key = self.api_key or os.getenv("SEARCHAPI_API_KEY", "")
        if not key:
            return "Warning: searchapi.io API key not configured; web search skipped."
        try:
            params = {"engine": "google", "q": query, "api_key": key, "num": "5", "gl": "us"}
            with httpx.Client(timeout=10) as client:
                r = client.get("https://www.searchapi.io/api/v1/search", params=params)
                r.raise_for_status()
                data = r.json()
                # Extract top titles/links succinctly
                items = []
                for res in (data.get("organic_results") or data.get("organic") or [])[:5]:
                    title = res.get("title")
                    link = res.get("link") or res.get("url")
                    if title and link:
                        items.append({"title": title, "link": link})
                return json.dumps(items, indent=2) if items else "Warning: no search results found."
        except Exception as e:
            logger.warning(f"searchapi.io error: {e!r}")
            return f"Warning: searchapi.io request failed: {e}"

    async def _arun(self, query: str, **kwargs: Any) -> str:
        return self._run(query, **kwargs)

