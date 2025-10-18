"""Cache manager for LLM and input mocker responses."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class CacheManager:
    """Manages file-based caching for LLM and input mocker responses."""

    _CACHE_DIR = Path.cwd() / ".uipath" / "eval_cache"

    @staticmethod
    def _compute_cache_key(cache_key_data: Dict[str, Any]) -> str:
        """Compute a hash from cache key data."""
        serialized = json.dumps(cache_key_data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _get_cache_path(
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key: str,
        function_name: Optional[str] = None,
    ) -> Path:
        """Get the file path for a cache entry.

        LLM mocker cache path: {cache_dir}/llm_mocker/{eval_set_id}/{eval_item_id}/{function_name}/{cache_key}.json
        Input mocker cache path: {cache_dir}/input_mocker/{eval_set_id}/{eval_item_id}/{cache_key}.json
        """
        if function_name:
            return (
                CacheManager._CACHE_DIR
                / mocker_type
                / eval_set_id
                / eval_item_id
                / function_name
                / f"{cache_key}.json"
            )
        else:
            return (
                CacheManager._CACHE_DIR
                / mocker_type
                / eval_set_id
                / eval_item_id
                / f"{cache_key}.json"
            )

    @staticmethod
    def get(
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key_data: Dict[str, Any],
        function_name: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve a cached response."""
        cache_key = CacheManager._compute_cache_key(cache_key_data)
        cache_path = CacheManager._get_cache_path(
            mocker_type, eval_set_id, eval_item_id, cache_key, function_name
        )

        if not cache_path.exists():
            return None

        with open(cache_path, "r") as f:
            cached_response = json.load(f)

        return cached_response

    @staticmethod
    def set(
        mocker_type: str,
        eval_set_id: str,
        eval_item_id: str,
        cache_key_data: Dict[str, Any],
        response: Any,
        function_name: Optional[str] = None,
    ) -> None:
        """Store a response in the cache."""
        cache_key = CacheManager._compute_cache_key(cache_key_data)
        cache_path = CacheManager._get_cache_path(
            mocker_type, eval_set_id, eval_item_id, cache_key, function_name
        )

        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w") as f:
            json.dump(response, f)
