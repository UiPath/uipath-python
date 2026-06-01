"""UiPath Skills.

Versioned, folder-scoped prompt resources stored in vdbs and exposed under
`/ecs_/v2/Skills`. Each published skill can be bound to an agent as a callable
tool whose Content is used as the system prompt for a sub-LLM call.
"""

from ._skills_service import SkillsService
from .skills import (
    Skill,
    SkillVersion,
    SkillVersionStatus,
    SkillVersionSummary,
    VersionBumpLevel,
)

__all__ = [
    "Skill",
    "SkillVersion",
    "SkillVersionStatus",
    "SkillVersionSummary",
    "SkillsService",
    "VersionBumpLevel",
]
