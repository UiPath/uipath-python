"""Tests for reading SKILL.md frontmatter."""

import pytest

from uipath.platform.skills._constants import MAX_DESCRIPTION_CHARS
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
        ("---\ndescription:\n---\n", ""),
        ("---\ndescription: [a, b]\n---\n", ""),
        ("---\ndescription: {a: b}\n---\n", ""),
        ("---\ndescription: 2026-11-20\n---\n", ""),
        ("---\ndescription: 42\n---\n", ""),
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
        "empty-value",
        "list",
        "mapping",
        "date",
        "number",
    ],
)
def test_parse_skill_description(content: str, expected: str) -> None:
    # The cases follow deepagents' frontmatter regex, ^---\s*\n(.*?)\n---\s*\n.
    assert parse_skill_description(content) == expected


def test_a_large_file_without_a_closing_fence_is_read_in_linear_time() -> None:
    # deepagents' regex backtracks for minutes on this.
    assert parse_skill_description("---\n" + "\n" * 200_000 + "x") == ""


def test_a_long_description_is_cut_to_the_limit() -> None:
    content = f"---\ndescription: {'x' * 5000}\n---\n"
    assert parse_skill_description(content) == "x" * MAX_DESCRIPTION_CHARS


def test_nested_aliases_are_not_expanded() -> None:
    # Ten aliases per level: str() of this would be millions of characters.
    lines = ["---", "a: &a [x, x, x, x, x, x, x, x, x, x]"]
    for prev, name in zip("abcde", "bcdef", strict=True):
        lines.append(f"{name}: &{name} [{', '.join([f'*{prev}'] * 10)}]")
    lines += ["description: *f", "---", ""]
    assert parse_skill_description("\n".join(lines)) == ""


def test_a_string_alias_is_kept() -> None:
    content = "---\nshared: &d Classify invoices.\ndescription: *d\n---\n"
    assert parse_skill_description(content) == "Classify invoices."
