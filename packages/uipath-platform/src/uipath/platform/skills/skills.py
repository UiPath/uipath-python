"""Skill bundle references, resolved bundles and the skills manifest."""

from __future__ import annotations

import json
import logging
import shutil
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._constants import (
    MANIFEST_FILE_NAME,
    OVERWRITE_TYPE,
    SKILL_FILE_NAME,
    SKILLS_DIR_NAME,
)
from ._layout import is_plain_name
from ._telemetry import record_skill_loaded

logger = logging.getLogger(__name__)


class VersionMode(StrEnum):
    """How a bundle version is chosen.

    ``pinned`` uses a fixed version; ``latest`` takes the newest one at run start.
    """

    # Keep in sync with the Literal on common._bindings.SkillBundleResourceOverwrite.
    PINNED = "pinned"
    LATEST = "latest"


class SkillBundleRef(BaseModel):
    """One bound skill bundle: what the agent asks the Skills API for."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str
    folder_path: str | None = Field(default=None, alias="folderPath")
    version_mode: VersionMode = Field(default=VersionMode.LATEST, alias="versionMode")
    version: str | None = None
    source_name: str | None = Field(default=None, alias="sourceName")
    """The deploy-time bundle name, when a binding points ``name`` elsewhere."""

    @field_validator("name", "source_name")
    @classmethod
    def _name_is_one_folder(cls, name: str | None) -> str | None:
        # The name becomes a folder under the set's root that is later removed
        # with rmtree; hidden names are refused so a bundle can't shadow the
        # manifest.
        if name is None:
            return None
        if not is_plain_name(name) or name != name.strip():
            raise ValueError("a skill bundle name must be a single folder name")
        return name

    @model_validator(mode="after")
    def _version_matches_mode(self) -> SkillBundleRef:
        if self.version_mode is VersionMode.LATEST:
            self.version = None
        elif not self.version:
            raise ValueError("a pinned skill bundle needs a version")
        return self

    @property
    def key(self) -> str:
        """The ``resourceOverwrites`` key, ``skillBundle.<name>``."""
        return f"{OVERWRITE_TYPE}.{self.name}"

    @property
    def lookup_name(self) -> str:
        """The bundle to fetch from Orchestrator or the local folder.

        ``name`` stays the bundle's identity for the agent (bundle folder,
        prompt label, manifest); a deploy-time binding only changes this.
        """
        return self.source_name or self.name


class Skill(BaseModel):
    """One skill a source wrote into its bundle folder.

    ``name`` equals the skill's folder name inside the bundle. ``name`` and every
    entry of ``files`` are checked to stay inside that folder; ``SkillSet.read``
    relies on it.
    """

    name: str
    description: str
    files: list[str] = Field(default_factory=list)
    """Paths relative to the skill folder in POSIX form, ``SKILL.md`` first."""

    @field_validator("name")
    @classmethod
    def _name_is_one_folder(cls, name: str) -> str:
        if not is_plain_name(name):
            raise ValueError("a skill name must be a single folder name")
        return name

    @field_validator("files")
    @classmethod
    def _files_stay_inside_the_folder(cls, files: list[str]) -> list[str]:
        for f in files:
            if not f or not all(is_plain_name(part) for part in f.split("/")):
                raise ValueError(f"skill file path escapes the skill folder: {f!r}")
        return files


class SkillBundle(BaseModel):
    """A bundle a source resolved to a concrete version and wrote to disk."""

    ref: SkillBundleRef
    version: str
    skills: list[Skill]

    @property
    def virtual_root(self) -> str:
        """The bundle folder as the agent sees it, ``/skills/<name>/``."""
        return f"/{SKILLS_DIR_NAME}/{self.ref.name}/"

    @property
    def label(self) -> str:
        """Display name with the resolved version, ``<name> v<version>``."""
        return f"{self.ref.name} v{self.version}"


FailureReason = Literal[
    "not_found",
    "version_not_found",
    "invalid",
    "too_large",
    "source_unavailable",
    "forbidden",
]
"""Why a bundle was skipped.

``invalid`` also covers stale files that could not be removed before materializing.
"""

InvokedBy = Literal["model", "user"]
"""Who asked for a skill: ``model`` for a tool call, ``user`` for the agent's own code."""


class BundleFailure(BaseModel):
    """A bound bundle that could not be materialized, and why."""

    ref: SkillBundleRef
    reason: FailureReason
    detail: str = ""


class SkillSet(BaseModel):
    """The skill bundles resolved for one run, and the bundles that could not be.

    ``save``/``load`` keep the set as ``.uipath-skills-manifest.json`` inside the
    folder the bundles were written to; ``root`` and ``owns_root`` never land in
    that manifest.
    """

    source: str
    """Where the bundles came from, for instance ``local`` or ``orchestrator``."""
    bundles: list[SkillBundle]
    failures: list[BundleFailure] = Field(default_factory=list)
    root: Path | None = Field(default=None, exclude=True)
    """Folder the bundles were written to; ``None`` before materializing and after ``cleanup``."""
    owns_root: bool = Field(default=False, exclude=True, repr=False)
    """Whether ``cleanup`` may remove ``root``: only for a temp folder this set created."""

    def names(self) -> list[str]:
        """Qualified ``<bundle>/<skill>`` names in bundle order (D20)."""
        return [f"{b.ref.name}/{s.name}" for b in self.bundles for s in b.skills]

    def find(self, qualified_name: str) -> tuple[SkillBundle, Skill] | None:
        """The bundle and skill a qualified ``<bundle>/<skill>`` name points to.

        Args:
            qualified_name: A name as ``names`` returns it.

        Returns:
            The matching bundle and skill, or ``None`` for an unknown name.
        """
        bundle_name, _, skill_name = qualified_name.partition("/")
        for bundle in self.bundles:
            if bundle.ref.name != bundle_name:
                continue
            for skill in bundle.skills:
                if skill.name == skill_name:
                    return bundle, skill
        return None

    def prompt_section(self) -> str:
        """``## Skills`` markdown listing every skill with its description, or ``""`` when no bundle has a skill."""
        if not any(bundle.skills for bundle in self.bundles):
            return ""
        lines = [
            "## Skills",
            "",
            "Skills are packaged instructions bound to this agent, grouped in bundles. "
            "Each skill is named `<bundle>/<skill>`. Load a skill's full instructions "
            "only when the task matches its description, then follow them step by "
            "step. Scripts inside a skill cannot be executed here; a skill may name "
            "tools you do not have — continue with the tools you have and say what "
            "was missing.",
            "",
        ]
        for bundle in self.bundles:
            for skill in bundle.skills:
                description = " ".join(skill.description.split())
                lines.append(
                    f"- **{bundle.ref.name}/{skill.name}** (bundle v{bundle.version}): "
                    f"{description}"
                )
        return "\n".join(lines)

    def read(
        self,
        qualified_name: str,
        path: str = SKILL_FILE_NAME,
        *,
        invoked_by: InvokedBy = "model",
    ) -> str:
        """A skill file's text. Reading ``SKILL.md`` records a skill-load span.

        Args:
            qualified_name: The ``<bundle>/<skill>`` name.
            path: A file the skill lists, in the POSIX form ``Skill.files`` uses,
                relative to the skill folder.
            invoked_by: Who asked for the file, for the span: ``"model"`` for a
                tool call, ``"user"`` when the agent's own code loaded it.

        Returns:
            The file text decoded as UTF-8, a BOM dropped. When the file is not
            valid UTF-8 a warning is logged and undecodable bytes are replaced.

        Raises:
            KeyError: Unknown skill, or a file the skill does not list.
            RuntimeError: The set has no ``root``: manifest only, or cleaned up.
        """
        hit = self.find(qualified_name)
        if hit is None:
            raise KeyError(qualified_name)
        bundle, skill = hit
        if path not in skill.files:
            raise KeyError(path)
        if self.root is None:
            raise RuntimeError(
                "this SkillSet was not materialized to disk, or was cleaned up"
            )
        file = self.root / bundle.ref.name / skill.name / path
        try:
            text = file.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as e:
            logger.warning(
                "Skill file %s is not valid UTF-8 (%s); replacing undecodable bytes",
                file,
                e,
            )
            text = file.read_text(encoding="utf-8-sig", errors="replace")
        if path == SKILL_FILE_NAME:
            record_skill_loaded(
                bundle, skill, size=len(text.encode("utf-8")), invoked_by=invoked_by
            )
        return text

    def cleanup(self) -> None:
        """Remove the temp root this set created; a caller-supplied destination is left alone.

        Afterwards the set has no ``root``, so ``read`` raises ``RuntimeError``
        and a second ``cleanup`` does nothing. A root that cannot be removed is
        logged as a warning.
        """
        if self.owns_root and self.root is not None:
            try:
                shutil.rmtree(self.root)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.warning("Could not remove skills folder %s: %s", self.root, e)
        self.owns_root = False
        self.root = None

    def skill_at(self, virtual_path: str) -> tuple[SkillBundle, Skill] | None:
        """The bundle and skill whose ``SKILL.md`` sits at ``virtual_path``.

        Args:
            virtual_path: A path in the agent's virtual filesystem; a relative
                path is read from the root, as a virtual filesystem backend does.

        Returns:
            The matching bundle and skill, or ``None`` when the path is not a
            ``SKILL.md`` of a materialized skill.
        """
        if not virtual_path.startswith("/"):
            virtual_path = f"/{virtual_path}"
        # ("/", "skills", <bundle>, <skill>, "SKILL.md")
        parts = PurePosixPath(virtual_path).parts
        if (
            len(parts) != 5
            or parts[1] != SKILLS_DIR_NAME
            or parts[4] != SKILL_FILE_NAME
        ):
            return None
        for bundle in self.bundles:
            if bundle.ref.name != parts[2]:
                continue
            for skill in bundle.skills:
                if skill.name == parts[3]:
                    return bundle, skill
        return None

    def save(self, skills_dir: Path) -> None:
        """Write the manifest into ``skills_dir``, creating the folder if needed.

        Args:
            skills_dir: The folder the bundles were written to.
        """
        skills_dir.mkdir(parents=True, exist_ok=True)
        with (skills_dir / MANIFEST_FILE_NAME).open(
            "w", encoding="utf-8", newline="\n"
        ) as manifest:
            manifest.write(self.model_dump_json(by_alias=True, indent=2))

    @classmethod
    def load(cls, skills_dir: Path) -> SkillSet | None:
        """Read the manifest from ``skills_dir``.

        The set comes back with ``root=skills_dir`` and ``owns_root=False``, so
        ``read`` works right away and ``cleanup`` leaves the folder alone. A
        ``root`` or ``owns_root`` key inside the file is ignored; ``save`` never
        writes them.

        Args:
            skills_dir: The folder the bundles were written to.

        Returns:
            The manifest, or ``None`` when the folder holds none.

        Raises:
            ValueError: If the manifest is not valid JSON (``json.JSONDecodeError``)
                or does not match the model (``pydantic.ValidationError``).
        """
        path = skills_dir / MANIFEST_FILE_NAME
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} does not hold a JSON object")
        data.pop("root", None)
        data.pop("owns_root", None)
        return cls.model_validate({**data, "root": skills_dir, "owns_root": False})
