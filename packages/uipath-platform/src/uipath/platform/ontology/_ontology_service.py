"""Ontology service: an ontology by id, its artifacts, its graph and SQL over it.

Backend target: ``ontology_/api/v1``. The ontology id is its key in the Resource
Catalog and in Solutions; the routes also accept the ontology's name, which is
folder-scoped, so an ``ontology`` binding can re-point a call to a name in a folder.

Honors ``UIPATH_SERVICE_URL_ONTOLOGY`` for local development, as every service
does: ``BaseService.request`` redirects the call and injects the routing headers.
"""

import asyncio
import logging
import uuid
from email.message import Message
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._models import Endpoint, RequestSpec
from .ontology import (
    ArtifactDownload,
    OntologyArtifact,
    OntologyArtifactContent,
    OntologyArtifactIntegrityError,
    OntologyDetails,
    SkippedArtifact,
    SqlResult,
)

logger = logging.getLogger(__name__)

_BASE = "ontology_/api/v1/ontology"

#: What ``download_artifacts`` puts in a prompt at most, per file.
DEFAULT_MAX_ARTIFACT_BYTES = 256_000

#: How many artifacts ``download_artifacts_async`` fetches at once.
MAX_CONCURRENT_DOWNLOADS = 4


def _folder_headers(
    folder_key: Optional[str], folder_path: Optional[str]
) -> Dict[str, str]:
    """Folder headers for a call, sending a folder key that arrived as a path.

    A deploy-time override carries the ontology's folder in ``folderPath``, and the
    Agents packager fills it with the folder key, a GUID. Sent as a path, the service
    would look up a folder by that name and answer 404, so a GUID goes as the key,
    as the entity planner does for the same binding shape.
    """
    if folder_key is None and folder_path and _is_guid(folder_path):
        return header_folder(folder_path, None)
    return header_folder(folder_key, folder_path)


def _is_guid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


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

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_artifact_by_type", run_type="uipath")
    def get_artifact_by_type(
        self,
        ontology_id: str,
        artifact_type: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyArtifactContent:
        """Download the one artifact of a single-file type, such as the schema.

        One request, no manifest: the service answers the type's file as a download by
        name does, and the content is verified against the checksum in its ETag.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            artifact_type: A single-file type: ``schema``, ``mapping``, ``summary`` or
                ``context``. A type that can hold several files is refused by the
                service; list those with :meth:`list_artifacts`.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            OntologyArtifactContent: the bytes, their media type, file name and ETag.

        Raises:
            OntologyArtifactIntegrityError: If the bytes do not match the ETag checksum.
        """
        spec = self._by_type_spec(ontology_id, artifact_type, folder_key, folder_path)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)
        return self._to_typed_content(artifact_type, response)

    @resource_override(
        resource_type="ontology",
        resource_identifier="ontology_id",
        folder_identifier="folder_path",
    )
    @traced(name="ontology_get_artifact_by_type", run_type="uipath")
    async def get_artifact_by_type_async(
        self,
        ontology_id: str,
        artifact_type: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> OntologyArtifactContent:
        """Download the one artifact of a single-file type. See :meth:`get_artifact_by_type`."""
        spec = self._by_type_spec(ontology_id, artifact_type, folder_key, folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return self._to_typed_content(artifact_type, response)

    @traced(name="ontology_download_artifacts", run_type="uipath")
    def download_artifacts(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ArtifactDownload:
        """Download every artifact of a type, verified against the manifest.

        Files larger than ``max_bytes`` are not downloaded. They come back in
        ``skipped`` with their size, so a caller can tell a file that was too large
        from one the ontology does not have.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            artifact_type: Keep one type only; every type when omitted.
            max_bytes: The largest file to download, by its manifest size.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            ArtifactDownload: the verified files in manifest order, and the entries
            skipped for size.
        """
        manifest = self.list_artifacts(
            ontology_id, artifact_type, folder_key=folder_key, folder_path=folder_path
        )
        kept, skipped = self._split_by_size(manifest, max_bytes)
        files = [
            self.get_artifact(
                ontology_id,
                entry.file_name,
                expected=entry,
                folder_key=folder_key,
                folder_path=folder_path,
            )
            for entry in kept
        ]
        return ArtifactDownload(files=files, skipped=skipped)

    @traced(name="ontology_download_artifacts", run_type="uipath")
    async def download_artifacts_async(
        self,
        ontology_id: str,
        artifact_type: Optional[str] = None,
        *,
        max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ArtifactDownload:
        """Download every artifact of a type. See :meth:`download_artifacts`.

        The files are fetched concurrently, at most ``MAX_CONCURRENT_DOWNLOADS`` at a
        time, and keep manifest order. Any failed or mismatched download fails the
        call, as in the sync variant.
        """
        manifest = await self.list_artifacts_async(
            ontology_id, artifact_type, folder_key=folder_key, folder_path=folder_path
        )
        kept, skipped = self._split_by_size(manifest, max_bytes)
        limit = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

        async def fetch(entry: OntologyArtifact) -> OntologyArtifactContent:
            async with limit:
                return await self.get_artifact_async(
                    ontology_id,
                    entry.file_name,
                    expected=entry,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )

        files = await asyncio.gather(*(fetch(entry) for entry in kept))
        return ArtifactDownload(files=list(files), skipped=skipped)

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
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> SqlResult:
        """Run one SELECT over the ontology's objects.

        The statement is written over business objects and their properties, with
        ``:name`` parameters bound from ``params``; the service translates it onto
        the mapped entities and runs it with the caller's permissions. Values go in
        ``params``, never in the statement text.

        Paging is part of the statement: without a LIMIT the service reads 50 rows,
        a LIMIT is at most 200, and OFFSET with ORDER BY reads a later page.

        Args:
            ontology_id: The ontology's id, or its name with a folder.
            statement: The SELECT, with ``:name`` placeholders.
            params: Values for the placeholders.
            folder_key: The key of the ontology's folder; needed when addressing by name.
            folder_path: The path of the ontology's folder; exclusive with ``folder_key``.

        Returns:
            SqlResult: columns, rows as objects, and the row count.

        Raises:
            ValueError: If the statement is blank.
        """
        spec = self._sql_spec(ontology_id, statement, params, folder_key, folder_path)
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
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> SqlResult:
        """Run one SELECT over the ontology's objects. See :meth:`execute_sql`."""
        spec = self._sql_spec(ontology_id, statement, params, folder_key, folder_path)
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
            headers=_folder_headers(folder_key, folder_path),
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
            headers=_folder_headers(folder_key, folder_path),
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
            headers=_folder_headers(folder_key, folder_path),
        )

    @staticmethod
    def _by_type_spec(
        ontology_id: str,
        artifact_type: str,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/artifact/type/"
                f"{_segment(artifact_type, 'artifact_type')}"
            ),
            headers=_folder_headers(folder_key, folder_path),
        )

    @staticmethod
    def _graph_spec(
        ontology_id: str, folder_key: Optional[str], folder_path: Optional[str]
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/graph"),
            headers=_folder_headers(folder_key, folder_path),
        )

    @staticmethod
    def _sql_spec(
        ontology_id: str,
        statement: str,
        params: Optional[Dict[str, Any]],
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_BASE}/{_segment(ontology_id, 'ontology_id')}/sql"),
            json={
                "statement": _checked_statement(statement),
                "params": params or {},
            },
            headers=_folder_headers(folder_key, folder_path),
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _split_by_size(
        manifest: List[OntologyArtifact], max_bytes: int
    ) -> Tuple[List[OntologyArtifact], List[SkippedArtifact]]:
        kept: List[OntologyArtifact] = []
        skipped: List[SkippedArtifact] = []
        for entry in manifest:
            if entry.size_bytes > max_bytes:
                logger.warning(
                    "Skipping ontology artifact %s: %d bytes is over the %d byte cap",
                    entry.file_name,
                    entry.size_bytes,
                    max_bytes,
                )
                skipped.append(
                    SkippedArtifact(
                        file_name=entry.file_name,
                        type=entry.type,
                        size_bytes=entry.size_bytes,
                        reason=f"over the {max_bytes} byte cap",
                    )
                )
                continue
            kept.append(entry)
        return kept, skipped

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

    @staticmethod
    def _to_typed_content(artifact_type: str, response: Any) -> OntologyArtifactContent:
        etag = response.headers.get("etag")
        content = OntologyArtifactContent(
            file_name=_attachment_file_name(response.headers.get("content-disposition"))
            or artifact_type,
            content=response.content,
            media_type=response.headers.get("content-type", ""),
            etag=etag,
            type=artifact_type,
        )
        checksum = (etag or "").strip().removeprefix("W/").strip('"').lower()
        if checksum and content.sha256() != checksum:
            raise OntologyArtifactIntegrityError(
                f"Artifact '{content.file_name}' checksum {content.sha256()} does not "
                f"match its ETag {checksum}"
            )
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


def _attachment_file_name(disposition: Optional[str]) -> Optional[str]:
    """The file name a ``Content-Disposition`` names, preferring the UTF-8 form."""
    if not disposition:
        return None
    message = Message()
    message["content-disposition"] = disposition
    return message.get_filename()


def _checked_statement(statement: str) -> str:
    """The statement without trailing whitespace or ``;``, once it is known not blank.

    Nothing is appended, so a trailing comment cannot swallow any clause.
    """
    if not statement or not statement.strip():
        raise ValueError("statement must be a non-empty SELECT")
    return statement.rstrip().rstrip(";")
