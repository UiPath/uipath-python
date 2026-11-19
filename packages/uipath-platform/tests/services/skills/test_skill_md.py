"""Tests for reading SKILL.md frontmatter."""

import pytest

from uipath.platform.skills._skill_md import parse_skill_description

FRONTMATTER = ["---", "name: triage", "description: Classify invoices.", "---", "# T"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("\n".join(FRONTMATTER), "Classify invoices."),
        ("\r\n".join(FRONTMATTER), "Classify invoices."),
        ("﻿" + "\n".join(FRONTMATTER), "Classify invoices."),
        ("﻿" + "\r\n".join(FRONTMATTER), "Classify invoices."),
        ("---\ndescription: '  padded  '\n---\n", "padded"),
        ("# Triage\n\nNo frontmatter here.\n", ""),
        ("---\n- a\n- b\n---\n", ""),
        ("---\nname: triage\n---\n", ""),
        ("---\nname: [unclosed\n---\n", ""),
        ("---\n\n\ndescription: y\n---\n", "y"),
        ("---\n\n---\ndescription: y\n---\n", "y"),
        ("---\ndescription: y\n---", ""),
    ],
    ids=[
        "lf",
        "crlf",
        "bom-lf",
        "bom-crlf",
        "stripped",
        "no-frontmatter",
        "not-a-mapping",
        "no-description",
        "invalid-yaml",
        "blank-lines-after-the-fence",
        "a-fence-after-blank-lines-starts-the-yaml",
        "the-closing-fence-needs-a-newline",
    ],
)
def test_parse_skill_description(content: str, expected: str) -> None:
    # The cases follow deepagents' frontmatter regex, ^---\s*\n(.*?)\n---\s*\n.
    assert parse_skill_description(content) == expected


def test_a_large_file_without_a_closing_fence_is_read_in_linear_time() -> None:
    # deepagents' regex backtracks for minutes on this.
    assert parse_skill_description("---\n" + "\n" * 200_000 + "x") == ""
