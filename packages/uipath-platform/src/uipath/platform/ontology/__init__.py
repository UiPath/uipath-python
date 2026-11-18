"""Ontology service package.

Provides the ``OntologyService`` client for reading a deployed ontology by id,
downloading the artifact files it was installed from, reading its graph and
running SQL over its objects, plus the Pydantic models for those answers.
"""

from ._ontology_service import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    MAX_SQL_LIMIT,
    OntologyService,
)
from .ontology import (
    ONTOLOGY_DEPLOYED_STATE,
    OntologyArtifact,
    OntologyArtifactContent,
    OntologyArtifactIntegrityError,
    OntologyDetails,
    SqlColumn,
    SqlResult,
)

__all__ = [
    "DEFAULT_MAX_ARTIFACT_BYTES",
    "MAX_SQL_LIMIT",
    "ONTOLOGY_DEPLOYED_STATE",
    "OntologyArtifact",
    "OntologyArtifactContent",
    "OntologyArtifactIntegrityError",
    "OntologyDetails",
    "OntologyService",
    "SqlColumn",
    "SqlResult",
]
