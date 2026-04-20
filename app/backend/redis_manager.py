import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as redis

logger = logging.getLogger("archaion.redis")

class RedisManager:
    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = None
        self._connected = False
        self._fallback_store: Dict[str, Any] = {}
        self._use_fallback = False

    async def connect(self):
        if not self._connected and not self._use_fallback:
            try:
                self.client = redis.from_url(self.url, decode_responses=True)
                await self.client.ping()
                self._connected = True
                logger.info(f"Connected to Redis at {self.url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {self.url}: {e}. Using local in-memory fallback.")
                self.client = None
                self._connected = False
                self._use_fallback = True

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self._connected = False
        self._fallback_store.clear()

    async def is_ready(self) -> bool:
        if not self._connected and not self._use_fallback:
            await self.connect()
        return self._connected or self._use_fallback

    async def set_execution_registry(self, execution_id: str, registry_data: Dict[str, Any], ttl: int = 7200):
        """Stores the dynamic MCP tools registry for the given execution."""
        if not await self.is_ready():
            return
        key = f"execution:{execution_id}:registry"
        try:
            if self._use_fallback:
                self._fallback_store[key] = json.dumps(registry_data)
            else:
                await self.client.setex(key, ttl, json.dumps(registry_data))
        except Exception as e:
            logger.error(f"Error setting registry for {execution_id}: {e}")

    async def get_execution_registry(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the dynamic MCP tools registry."""
        if not await self.is_ready():
            return None
        key = f"execution:{execution_id}:registry"
        try:
            if self._use_fallback:
                data = self._fallback_store.get(key)
            else:
                data = await self.client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error getting registry for {execution_id}: {e}")
        return None

    async def store_tool_output(self, execution_id: str, tool_name: str, call_id: str, payload: Any, ttl: int = 7200):
        """Stores cleaned tool payload in Redis to prevent context window bloat."""
        if not await self.is_ready():
            return
        key = f"execution:{execution_id}:data:{tool_name}:{call_id}"
        try:
            # Store as JSON string
            if not isinstance(payload, str):
                payload = json.dumps(payload)
            if self._use_fallback:
                self._fallback_store[key] = payload
            else:
                await self.client.setex(key, ttl, payload)
        except Exception as e:
            logger.error(f"Error storing tool output for {execution_id} ({tool_name}): {e}")

    async def get_tool_output(self, execution_id: str, tool_name: str, call_id: str) -> Optional[Any]:
        """Retrieves previously stored tool output."""
        if not await self.is_ready():
            return None
        key = f"execution:{execution_id}:data:{tool_name}:{call_id}"
        try:
            if self._use_fallback:
                data = self._fallback_store.get(key)
            else:
                data = await self.client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error getting tool output for {execution_id} ({tool_name}): {e}")
        return None

    async def get_all_execution_data(self, execution_id: str) -> Dict[str, Any]:
        """Retrieves all intermediate data stored during an execution for final synthesis."""
        if not await self.is_ready():
            return {}
        
        pattern = f"execution:{execution_id}:data:*"
        result = {}
        try:
            if self._use_fallback:
                keys = [k for k in self._fallback_store.keys() if k.startswith(f"execution:{execution_id}:data:")]
            else:
                keys = await self.client.keys(pattern)
            for key in keys:
                # Key format: execution:<id>:data:<tool_name>:<call_id>
                parts = key.split(":")
                if len(parts) >= 5:
                    tool_name = parts[3]
                    call_id = parts[4]
                    if self._use_fallback:
                        val = self._fallback_store.get(key)
                    else:
                        val = await self.client.get(key)
                    if val:
                        if tool_name not in result:
                            result[tool_name] = []
                        result[tool_name].append({
                            "call_id": call_id,
                            "data": json.loads(val)
                        })
        except Exception as e:
            logger.error(f"Error fetching all data for {execution_id}: {e}")
        
        return result

# Global instance
redis_client = RedisManager()
