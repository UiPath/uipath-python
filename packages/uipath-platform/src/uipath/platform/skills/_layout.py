"""The on-disk bundle layout, ``<bundle>/<skill>/SKILL.md`` plus an optional ``bundle.json``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ._constants import BUNDLE_FILE_NAME, LOCAL_VERSION, SKILL_FILE_NAME

logger = logging.getLogger(__name__)


def read_bundle_version(bundle_dir: Path) -> str:
    """The ``version`` from ``bundle.json``, as a string.

    Args:
        bundle_dir: The bundle folder.

    Returns:
        The version, or ``LOCAL_VERSION`` when ``bundle.json`` is missing,
        unreadable, not a JSON object, or has an empty or null ``version``.
    """
    try:
        data = json.loads((bundle_dir / BUNDLE_FILE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return LOCAL_VERSION
    except (ValueError, OSError) as e:
        logger.warning(
            "Ignoring unreadable %s in %s: %s", BUNDLE_FILE_NAME, bundle_dir, e
        )
        return LOCAL_VERSION
    if not isinstance(data, dict):
        logger.warning(
            "Ignoring %s in %s: not a JSON object", BUNDLE_FILE_NAME, bundle_dir
        )
        return LOCAL_VERSION
    version = data.get("version")
    if version is None or version == "":
        return LOCAL_VERSION
    return str(version)


def is_plain_name(name: str) -> bool:
    r"""Whether ``name`` is one visible path segment.

    Args:
        name: A file or folder name, or one segment of a relative path.

    Returns:
        ``False`` when it is empty, hidden (which covers ``.`` and ``..``), or
        contains a separator, a drive colon or a NUL byte (``/``, ``\``, ``:``,
        ``\0``). A NUL is refused because ``Path.resolve`` raises ``ValueError``
        for it on Windows, which no caller expects from a path.
    """
    return (
        bool(name)
        and not name.startswith(".")
        and not any(c in name for c in "/\\:\x00")
    )


def is_skill_md(path: str) -> bool:
    """Whether ``path``, relative to a skill folder, names its ``SKILL.md`` in any case.

    Args:
        path: A file path relative to the skill folder, in POSIX form.

    Returns:
        ``True`` for ``SKILL.md``, ``skill.md``, ``Skill.md`` and so on, at the
        top of the skill folder only.
    """
    return path.casefold() == SKILL_FILE_NAME.casefold()


def find_skill_md(path: Path) -> Path | None:
    """The ``SKILL.md`` of a skill folder, matched case-insensitively.

    A skill folder is a plain-named folder holding ``SKILL.md`` in any case
    (``skill.md`` counts). On a case-sensitive file system it can hold several
    spellings; ``SKILL.md`` itself wins, then the first in code-point order.

    Args:
        path: A child of a bundle folder.

    Returns:
        The file, or ``None`` when ``path`` is not a skill folder.
    """
    if not path.is_dir() or not is_plain_name(path.name):
        return None
    matches = [p for p in path.iterdir() if is_skill_md(p.name) and p.is_file()]
    return min(matches, key=lambda p: (p.name != SKILL_FILE_NAME, p.name), default=None)


def skill_md_first(path: str) -> tuple[bool, str]:
    """Sort key that puts ``SKILL.md``, in any case, before the other files of a skill.

    Args:
        path: A file path relative to the skill folder, in POSIX form.

    Returns:
        A key that orders ``SKILL.md`` first and the rest alphabetically.
    """
    return (not is_skill_md(path), path)


def iter_skill_files(skill_dir: Path) -> list[str]:
    """The files of a skill, relative to ``skill_dir`` in POSIX form.

    Args:
        skill_dir: A skill folder.

    Returns:
        Sorted paths with ``SKILL.md`` first; a path with any component that is
        not a plain name (hidden files and folders, for instance) is left out.
    """
    return sorted(
        (
            rel.as_posix()
            for rel in (
                p.relative_to(skill_dir) for p in skill_dir.rglob("*") if p.is_file()
            )
            if all(is_plain_name(part) for part in rel.parts)
        ),
        key=skill_md_first,
    )
