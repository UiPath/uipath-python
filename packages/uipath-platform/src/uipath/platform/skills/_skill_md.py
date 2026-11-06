"""Read the parts of a ``SKILL.md`` the SDK needs."""

from __future__ import annotations

import yaml

_BOM = "﻿"
_FENCE = "---"


def _frontmatter(content: str) -> str | None:
    r"""The YAML between the opening and the closing ``---`` line, or ``None``.

    Reads frontmatter as deepagents' SkillsMiddleware (the Agent Skills
    convention) does with ``^---\s*\n(.*?)\n---\s*\n``, without that regex,
    which backtracks on large inputs. Fence lines may carry trailing
    whitespace, ``\r`` included. Blank lines right after the opening fence are
    skipped, the first fence line after the first non-blank one closes the
    block, and a newline must follow the closing fence.
    """
    lines = content.split("\n")
    if lines[0].rstrip() != _FENCE:
        return None
    start = 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    # The last element follows the final newline, so it cannot close.
    for end in range(start + 1, len(lines) - 1):
        if lines[end].rstrip() == _FENCE:
            return "\n".join(lines[start:end])
    return None


def parse_skill_description(content: str) -> str:
    """The ``description`` from a ``SKILL.md``'s YAML frontmatter.

    Full frontmatter validation is left to the consumer of the skill.

    Args:
        content: The ``SKILL.md`` text; a leading UTF-8 BOM is ignored.

    Returns:
        The stripped description, or ``""`` when there is no frontmatter, it is
        not valid YAML, it is not a mapping, or it has no description.
    """
    frontmatter = _frontmatter(content.lstrip(_BOM))
    if frontmatter is None:
        return ""
    try:
        data = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("description", "")).strip()
