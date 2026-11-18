"""Ontology service package.

Provides the ``OntologyService`` client for reading a deployed ontology by id,
downloading the artifact files it was installed from, reading its graph and
running SQL over its objects, plus the Pydantic models for those answers.
"""

from ._ontology_service import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    OntologyService,
)
from .ontology import (
    ONTOLOGY_DEPLOYED_STATE,
    ArtifactDownload,
    OntologyArtifact,
    OntologyArtifactContent,
    OntologyArtifactIntegrityError,
    OntologyDetails,
    SkippedArtifact,
    SqlColumn,
    SqlResult,
)

__all__ = [
    "ArtifactDownload",
    "DEFAULT_MAX_ARTIFACT_BYTES",
    "ONTOLOGY_DEPLOYED_STATE",
    "OntologyArtifact",
    "OntologyArtifactContent",
    "OntologyArtifactIntegrityError",
    "OntologyDetails",
    "OntologyService",
    "SkippedArtifact",
    "SqlColumn",
    "SqlResult",
]
