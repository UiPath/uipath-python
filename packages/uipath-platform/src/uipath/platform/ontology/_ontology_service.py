"""Ontology service: an ontology by id, its artifacts, its graph and SQL over it.

Backend target: ``ontology_/api/v1``. The ontology id is its key in the Resource
Catalog and in Solutions; the routes also accept the ontology's name, which is
folder-scoped, so an ``ontology`` binding can re-point a call to a name in a folder.

Honors ``UIPATH_SERVICE_URL_ONTOLOGY`` for local development, as every service
does: ``BaseService.request`` redirects the call and injects the routing headers.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._models import Endpoint, RequestSpec
from .ontology import (
    OntologyArtifact,
    OntologyArtifactContent,
    OntologyArtifactIntegrityError,
    OntologyDetails,
    SqlResult,
)

logger = logging.getLogger(__name__)

_BASE = "ontology_/api/v1/ontology"

#: What ``download_artifacts`` puts in a prompt at most, per file.
DEFAULT_MAX_ARTIFACT_BYTES = 256_000

#: The service reads 50 rows without a LIMIT and caps a LIMIT at 200.
MAX_SQL_LIMIT = 200

_HAS_LIMIT = re.compile(r"\blimit\b", re.IGNORECASE)
_HAS_OFFSET = re.compile(r"\boffset\b", re.IGNORECASE)


def _segment(value: str, what: str) -> str:
    """One URL path segment, encoded so an id or file name can never add a path."""
    if not value or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return quote(value, safe="")


class OntologyService(BaseService):
    """Service for reading a deployed ontology and querying its objects.

    Every method takes the ontology's id. An ``ontology`` binding can replace that
    id with an ontology name and a folder; names are folder-scoped on the service,
    so the folder travels as the folder header.

    !!! warning "Preview Feature"
        This service is currently experimental. Behavior and parameters are
        subject to change in future versions.

    Examples:
        ```python
        from uipath.platform import UiPath

        sdk = UiPath()
        details = await sdk.ontology.get_async(ontology_id)
        if details.is_deployed:
            files = await sdk.ontology.download_artifacts_async(ontology_id, "schema")
            answer = await sdk.ontology.execute_sql_async(
                ontology_id, "SELECT name FROM Supplier WHERE country = :c", {"c": "RO"}
            )
        ```
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    # ── details ──────────────────────────────────────────────────────────

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get", run_type="uipath")
    def get(
        self,
        ontology_id: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyDetails:
        """Read an ontology's catalog details.

        Args:
            ontology_id: The ontology's id (its Resource Catalog key), or its name
                together with the folder it lives in.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            OntologyDetails: identifier, label, description, folder and state.
        """
        spec = self._details_spec(ontology_id, folder_key, folder_path)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)
        return OntologyDetails.model_validate(response.json())

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get", run_type="uipath")
    async def get_async(
        self,
        ontology_id: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyDetails:
        """Read an ontology's catalog details. See :meth:`get`."""
        spec = self._details_spec(ontology_id, folder_key, folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return OntologyDetails.model_validate(response.json())

    # ── artifacts ────────────────────────────────────────────────────────

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_list_artifacts", run_type="uipath")
    def list_artifacts(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[OntologyArtifact]:
        """List an ontology's artifacts: the manifest, without content.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            artifact_type: Keep one type only: ``schema``, ``mapping``,
                ``business-rules``, ``summary``, ``context`` (or ``constraints``).
                The service answers 400 for an unknown type.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            List[OntologyArtifact]: one entry per file, with size and SHA-256.
        """
        spec = self._manifest_spec(ontology_id, artifact_type, folder_key, folder_path)
        response = self.request(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        )
        return [OntologyArtifact.model_validate(item) for item in response.json()]

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_list_artifacts", run_type="uipath")
    async def list_artifacts_async(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[OntologyArtifact]:
        """List an ontology's artifacts. See :meth:`list_artifacts`."""
        spec = self._manifest_spec(ontology_id, artifact_type, folder_key, folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        )
        return [OntologyArtifact.model_validate(item) for item in response.json()]

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_artifact", run_type="uipath")
    def get_artifact(
        self,
        ontology_id: str,
        file_name: str,
        *,
        expected: Optional[OntologyArtifact] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyArtifactContent:
        """Download one artifact's bytes.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            file_name: The artifact's file name, as the manifest lists it.
            expected: The manifest entry to verify the download against. When given,
                a size or SHA-256 mismatch raises before the content is returned.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            OntologyArtifactContent: the bytes, their media type and the ETag.

        Raises:
            OntologyArtifactIntegrityError: If ``expected`` is given and the bytes
                do not match it.
        """
        spec = self._download_spec(ontology_id, file_name, folder_key, folder_path)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)
        return self._to_content(file_name, response, expected)

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_artifact", run_type="uipath")
    async def get_artifact_async(
        self,
        ontology_id: str,
        file_name: str,
        *,
        expected: Optional[OntologyArtifact] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyArtifactContent:
        """Download one artifact's bytes. See :meth:`get_artifact`."""
        spec = self._download_spec(ontology_id, file_name, folder_key, folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return self._to_content(file_name, response, expected)

    @traced(name="ontology_download_artifacts", run_type="uipath")
    def download_artifacts(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[OntologyArtifactContent]:
        """Download every artifact of a type, verified against the manifest.

        Files larger than ``max_bytes`` are skipped with a warning, since they are
        meant for a prompt and would not fit.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            artifact_type: Keep one type only; every type when omitted.
            max_bytes: The largest file to download, by its manifest size.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            List[OntologyArtifactContent]: the verified files, in manifest order.
        """
        manifest = self.list_artifacts(
            ontology_id, artifact_type, folder_key=folder_key, folder_path=folder_path
        )
        contents: List[OntologyArtifactContent] = []
        for entry in self._within_budget(manifest, max_bytes):
            contents.append(
                self.get_artifact(
                    ontology_id,
                    entry.file_name,
                    expected=entry,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
            )
        return contents

    @traced(name="ontology_download_artifacts", run_type="uipath")
    async def download_artifacts_async(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[OntologyArtifactContent]:
        """Download every artifact of a type. See :meth:`download_artifacts`."""
        manifest = await self.list_artifacts_async(
            ontology_id, artifact_type, folder_key=folder_key, folder_path=folder_path
        )
        contents: List[OntologyArtifactContent] = []
        for entry in self._within_budget(manifest, max_bytes):
            contents.append(
                await self.get_artifact_async(
                    ontology_id,
                    entry.file_name,
                    expected=entry,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
            )
        return contents

    # ── graph ────────────────────────────────────────────────────────────

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_graph", run_type="uipath")
    def get_graph(
        self,
        ontology_id: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read the ontology's graph: objects, properties, relationships, operations.

        Returned as the service sends it, since its shape is still evolving.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            Dict[str, Any]: the graph view.
        """
        spec = self._graph_spec(ontology_id, folder_key, folder_path)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)
        return response.json()

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_graph", run_type="uipath")
    async def get_graph_async(
        self,
        ontology_id: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read the ontology's graph. See :meth:`get_graph`."""
        spec = self._graph_spec(ontology_id, folder_key, folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return response.json()

    # ── SQL ──────────────────────────────────────────────────────────────

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_execute_sql", run_type="uipath")
    def execute_sql(
        self,
        ontology_id: str,
        statement: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> SqlResult:
        """Run one SELECT over the ontology's objects.

        The statement is written over business objects and their properties, with
        ``:name`` parameters bound from ``params``; the service translates it onto
        the mapped entities and runs it with the caller's permissions. Values go in
        ``params``, never in the statement text.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            statement: The SELECT, with ``:name`` placeholders.
            params: Values for the placeholders.
            limit: Rows to read, at most 200. Without one the service reads 50.
                Appended as a LIMIT clause; the statement must not have one already.
            offset: Rows to skip, for a later page; pair with ORDER BY. Appended as
                an OFFSET clause; the statement must not have one already.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            SqlResult: columns, rows as objects, and the row count.

        Raises:
            ValueError: If the statement is blank, a bound is out of range, or a
                bound is given for a statement that already has that clause.
        """
        spec = self._sql_spec(
            ontology_id, statement, params, limit, offset, folder_key, folder_path
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return SqlResult.model_validate(response.json())

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_execute_sql", run_type="uipath")
    async def execute_sql_async(
        self,
        ontology_id: str,
        statement: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> SqlResult:
        """Run one SELECT over the ontology's objects. See :meth:`execute_sql`."""
        spec = self._sql_spec(
            ontology_id, statement, params, limit, offset, folder_key, folder_path
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return SqlResult.model_validate(response.json())

    # ── specs ────────────────────────────────────────────────────────────

    @staticmethod
    def _details_spec(
        ontology_id: str, folder_key: Optional[str], folder_path: Optional[str]
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_BASE}/{_segment(ontology_id, 'ontology_id')}"),
            headers=header_folder(folder_key, folder_path),
        )

    @staticmethod
    def _manifest_spec(
        ontology_id: str,
        artifact_type: Optional[str],
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        params: Dict[str, Any] = {}
        if artifact_type:
            params["type"] = artifact_type
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/artifact"
            ),
            params=params,
            headers=header_folder(folder_key, folder_path),
        )

    @staticmethod
    def _download_spec(
        ontology_id: str,
        file_name: str,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/artifact/"
                f"{_segment(file_name, 'file_name')}"
            ),
            headers=header_folder(folder_key, folder_path),
        )

    @staticmethod
    def _graph_spec(
        ontology_id: str, folder_key: Optional[str], folder_path: Optional[str]
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/graph"),
            headers=header_folder(folder_key, folder_path),
        )

    @staticmethod
    def _sql_spec(
        ontology_id: str,
        statement: str,
        params: Optional[Dict[str, Any]],
        limit: Optional[int],
        offset: Optional[int],
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/sql"),
            json={
                "statement": _bounded_statement(statement, limit, offset),
                "params": params or {},
            },
            headers=header_folder(folder_key, folder_path),
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _within_budget(
        manifest: List[OntologyArtifact], max_bytes: int
    ) -> List[OntologyArtifact]:
        kept: List[OntologyArtifact] = []
        for entry in manifest:
            if entry.size_bytes > max_bytes:
                logger.warning(
                    "Skipping ontology artifact %s: %d bytes is over the %d byte cap",
                    entry.file_name,
                    entry.size_bytes,
                    max_bytes,
                )
                continue
            kept.append(entry)
        return kept

    @staticmethod
    def _to_content(
        file_name: str, response: Any, expected: Optional[OntologyArtifact]
    ) -> OntologyArtifactContent:
        content = OntologyArtifactContent(
            file_name=file_name,
            content=response.content,
            media_type=response.headers.get("content-type", ""),
            etag=response.headers.get("etag"),
            type=expected.type if expected else None,
        )
        if expected is not None:
            _verify(content, expected)
        return content


def _verify(content: OntologyArtifactContent, expected: OntologyArtifact) -> None:
    """Refuse content whose size or SHA-256 differs from the manifest entry."""
    if len(content.content) != expected.size_bytes:
        raise OntologyArtifactIntegrityError(
            f"Artifact '{expected.file_name}' is {len(content.content)} bytes, "
            f"the manifest says {expected.size_bytes}"
        )
    digest = content.sha256()
    if digest != expected.checksum.lower():
        raise OntologyArtifactIntegrityError(
            f"Artifact '{expected.file_name}' checksum {digest} does not match "
            f"the manifest's {expected.checksum}"
        )


def _bounded_statement(
    statement: str, limit: Optional[int], offset: Optional[int]
) -> str:
    """The statement with LIMIT and OFFSET appended as integers, never as text.

    The service takes paging from the statement itself, so the bounds become
    clauses; they are validated integers, so nothing from the caller is spliced in
    as SQL text.
    """
    if not statement or not statement.strip():
        raise ValueError("statement must be a non-empty SELECT")
    bounded = statement.rstrip().rstrip(";")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an int")
        if not 1 <= limit <= MAX_SQL_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_SQL_LIMIT}")
        if _HAS_LIMIT.search(bounded):
            raise ValueError("statement already has a LIMIT; pass one or the other")
        bounded = f"{bounded} LIMIT {int(limit)}"
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("offset must be an int")
        if offset < 0:
            raise ValueError("offset must be 0 or more")
        if _HAS_OFFSET.search(bounded):
            raise ValueError("statement already has an OFFSET; pass one or the other")
        bounded = f"{bounded} OFFSET {int(offset)}"
    return bounded
