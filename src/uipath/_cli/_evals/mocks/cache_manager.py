"""Cache manager for LLM and input mocker responses."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Set


class CacheManager:
    """Manages caching for LLM and input mocker responses."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the cache manager with in-memory cache."""
        self.cache_dir = cache_dir or (Path.cwd() / ".uipath" / "eval_cache")
        self._memory_cache: Dict[str, Any] = {}
        self._dirty_keys: Set[str] = set()

    def _compute_cache_key(self, cache_key_data: Dict[str, Any]) -> str:
        """Compute a hash from cache key data."""
        serialized = json.dumps(cache_key_data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _get_cache_key_string(
        self,
        mocker_type: str,
        cache_key_data: Dict[str, Any],
        function_name: str,
    ) -> str:
        """Generate unique cache key string for memory lookup."""
        cache_key_hash = self._compute_cache_key(cache_key_data)
        return f"{mocker_type}/{function_name}/{cache_key_hash}"

    def _get_cache_path(
        self,
        cache_key_string: str,
    ) -> Path:
        """Get the file path for a cache entry from cache key string."""
        return self.cache_dir / f"{cache_key_string}.json"

    def get(
        self,
        mocker_type: str,
        cache_key_data: Dict[str, Any],
        function_name: str,
    ) -> Optional[Any]:
        """Retrieve a cached response from memory first, then disk."""
        cache_key_string = self._get_cache_key_string(
            mocker_type, cache_key_data, function_name
        )

        # Check memory cache first
        if cache_key_string in self._memory_cache:
            return self._memory_cache[cache_key_string]

        # Check disk cache
        cache_path = self._get_cache_path(cache_key_string)
        if not cache_path.exists():
            return None

        with open(cache_path, "r") as f:
            cached_response = json.load(f)

        # Populate memory cache
        self._memory_cache[cache_key_string] = cached_response
        return cached_response

    def set(
        self,
        mocker_type: str,
        cache_key_data: Dict[str, Any],
        response: Any,
        function_name: str,
    ) -> None:
        """Store a response in memory cache and mark for later disk write."""
        cache_key_string = self._get_cache_key_string(
            mocker_type, cache_key_data, function_name
        )

        # Store in memory
        self._memory_cache[cache_key_string] = response

        # Mark as dirty for later flush
        self._dirty_keys.add(cache_key_string)

    def flush(self) -> None:
        """Write all dirty cache entries to disk."""
        for cache_key_string in self._dirty_keys:
            cache_path = self._get_cache_path(cache_key_string)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_path, "w") as f:
                json.dump(self._memory_cache[cache_key_string], f)

        self._dirty_keys.clear()
