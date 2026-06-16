"""The ``uipath.com/job`` ``_meta`` contract (framework- and MCP-SDK-neutral).

All proprietary signaling for long-running UiPath jobs over MCP rides ``_meta``
under the single key ``uipath.com/job``:

* **Advertise** (server → client, ``InitializeResult._meta``): ``{"version": N}``
  — present only when the server can back tools with jobs.
* **START** (client → server, request ``params._meta``): ``{"version": N}`` — no
  ``key`` means "start the job and hand me a handle".
* **Handle** (server → client, result ``_meta``): ``{"key", "folderKey"}`` — the
  started job.
* **FETCH** (client → server, request ``params._meta``): ``{"key", "folderKey"}``
  — ``key`` present means "return the job's current status/result".

These helpers build and parse that key as plain ``dict`` / ``Mapping`` values, so
they work against any MCP SDK version (the wire ``_meta`` is a plain JSON object)
without importing ``mcp``.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ._handle import UiPathJobHandle

__all__ = [
    "JOB_META_KEY",
    "JOB_PROTOCOL_VERSION",
    "build_fetch_meta",
    "build_start_meta",
    "read_job_handle",
    "read_job_version",
]

JOB_META_KEY = "uipath.com/job"
"""Reverse-DNS ``_meta`` key under which all job signaling lives."""

JOB_PROTOCOL_VERSION = 1
"""Current ``uipath.com/job`` contract version emitted by this client."""


def build_start_meta(version: int = JOB_PROTOCOL_VERSION) -> Dict[str, Any]:
    """Build the START opt-in ``_meta`` (no ``key`` ⇒ START intent).

    Args:
        version: The contract version to send on the call.

    Returns:
        A ``_meta`` mapping to merge into ``CallToolRequest.params._meta``.
    """
    return {JOB_META_KEY: {"version": version}}


def build_fetch_meta(handle: UiPathJobHandle) -> Dict[str, Any]:
    """Build the FETCH ``_meta`` for a started job (``key`` present ⇒ FETCH intent).

    Args:
        handle: The job handle returned by the START response.

    Returns:
        A ``_meta`` mapping to merge into ``CallToolRequest.params._meta``.
    """
    return {JOB_META_KEY: {"key": handle.job_key, "folderKey": handle.folder_key}}


def _job_section(meta: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """Return the ``uipath.com/job`` sub-object of a ``_meta`` mapping, if present."""
    if not meta:
        return None
    section = meta.get(JOB_META_KEY)
    return section if isinstance(section, Mapping) else None


def read_job_handle(meta: Optional[Mapping[str, Any]]) -> Optional[UiPathJobHandle]:
    """Parse a job handle from a result's ``_meta`` mapping.

    Args:
        meta: The result ``_meta`` mapping (``result._meta`` / ``result.meta``).

    Returns:
        A :class:`UiPathJobHandle` when both ``key`` and ``folderKey`` are present
        (a START response), else ``None`` (a normal result, or a version-only
        opt-in echoed back).
    """
    section = _job_section(meta)
    if not section:
        return None
    key = section.get("key")
    folder_key = section.get("folderKey")
    if isinstance(key, str) and key and isinstance(folder_key, str) and folder_key:
        return UiPathJobHandle(job_key=key, folder_key=folder_key)
    return None


def read_job_version(meta: Optional[Mapping[str, Any]]) -> Optional[int]:
    """Parse the advertised / opted-in contract version from a ``_meta`` mapping.

    Args:
        meta: A ``_meta`` mapping (an ``InitializeResult._meta`` advertisement, or
            a request opt-in).

    Returns:
        The integer ``version`` when present, else ``None``.
    """
    section = _job_section(meta)
    if not section:
        return None
    version = section.get("version")
    return version if isinstance(version, int) else None
