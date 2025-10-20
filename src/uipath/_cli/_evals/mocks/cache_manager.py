"""Cache manager for LLM and input mocker responses."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class CacheManager:
    """Manages file-based caching for LLM and input mocker responses."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the cache manager."""
        self.cache_dir = cache_dir or (Path.cwd() / ".uipath" / "eval_cache")

    def _compute_cache_key(self, cache_key_data: Dict[str, Any]) -> str:
        """Compute a hash from cache key data."""
        serialized = json.dumps(cache_key_data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _get_cache_path(
        self,
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key: str,
        function_name: str,
    ) -> Path:
        """Get the file path for a cache entry."""
        return (
            self.cache_dir
            / mocker_type
            / eval_set_id
            / eval_item_id
            / function_name
            / f"{cache_key}.json"
        )

    def get(
        self,
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key_data: Dict[str, Any],
        function_name: str,
    ) -> Optional[Any]:
        """Retrieve a cached response."""
        cache_key = self._compute_cache_key(cache_key_data)
        cache_path = self._get_cache_path(
            mocker_type, eval_set_id, eval_item_id, cache_key, function_name
        )

        if not cache_path.exists():
            return None

        with open(cache_path, "r") as f:
            cached_response = json.load(f)

        return cached_response

    def set(
        self,
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key_data: Dict[str, Any],
        response: Any,
        function_name: str,
    ) -> None:
        """Store a response in the cache."""
        cache_key = self._compute_cache_key(cache_key_data)
        cache_path = self._get_cache_path(
            mocker_type, eval_set_id, eval_item_id, cache_key, function_name
        )

        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w") as f:
            json.dump(response, f)
