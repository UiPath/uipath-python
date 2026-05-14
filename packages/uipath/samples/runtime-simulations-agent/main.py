"""Coding agent that reviews code and suggests improvements.

This sample demonstrates the --simulation flag: the three tool functions
(check_syntax, check_style, suggest_improvements) are decorated with @mockable,
so they can be intercepted by an LLM during a simulated run instead of
requiring a real linter or compiler to be installed.

Run with real tools:
    uipath run main.py:main -f input.json

Run with simulation (no real tools needed):
    uipath run main.py:main -f input.json --simulation "$(cat simulation.json)"
"""

import logging

from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from uipath.eval.mocks import ExampleCall, mockable
from uipath.tracing import traced

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


@dataclass
class CodeReviewInput:
    code: str
    language: str = "python"


class SyntaxResult(BaseModel):
    valid: bool
    errors: list[str] = []


class StyleResult(BaseModel):
    score: int  # 0-100
    violations: list[str] = []


class ImprovementResult(BaseModel):
    suggestions: list[str] = []
    refactored_snippet: str = ""


class CodeReviewOutput(BaseModel):
    syntax: SyntaxResult
    style: StyleResult
    improvements: ImprovementResult
    summary: str


# ---------------------------------------------------------------------------
# Mockable tool functions
# ---------------------------------------------------------------------------

CHECK_SYNTAX_EXAMPLES = [
    ExampleCall(
        id="valid-python",
        input='{"code": "def hello():\\n    return 42", "language": "python"}',
        output='{"valid": true, "errors": []}',
    ),
    ExampleCall(
        id="syntax-error",
        input='{"code": "def hello(\\n    return 42", "language": "python"}',
        output='{"valid": false, "errors": ["SyntaxError: unexpected EOF"]}',
    ),
]


@traced(name="check_syntax", span_type="tool")
@mockable(example_calls=CHECK_SYNTAX_EXAMPLES)
async def check_syntax(code: str, language: str = "python") -> SyntaxResult:
    """Check code for syntax errors using the language's parser.

    Args:
        code: Source code to check.
        language: Programming language (default: python).

    Returns:
        SyntaxResult with valid flag and list of error messages.
    """
    if language != "python":
        return SyntaxResult(valid=True, errors=[])

    try:
        compile(code, "<string>", "exec")
        return SyntaxResult(valid=True, errors=[])
    except SyntaxError as exc:
        return SyntaxResult(valid=False, errors=[str(exc)])


CHECK_STYLE_EXAMPLES = [
    ExampleCall(
        id="clean-code",
        input='{"code": "def hello():\\n    return 42\\n", "language": "python"}',
        output='{"score": 95, "violations": []}',
    ),
    ExampleCall(
        id="style-issues",
        input='{"code": "def hello( ):\\n  return 42", "language": "python"}',
        output='{"score": 60, "violations": ["E211 whitespace before \'(\'", "W291 trailing whitespace"]}',
    ),
]


@traced(name="check_style", span_type="tool")
@mockable(example_calls=CHECK_STYLE_EXAMPLES)
async def check_style(code: str, language: str = "python") -> StyleResult:
    """Run style checks (e.g. PEP 8 for Python) on the provided code.

    Args:
        code: Source code to check.
        language: Programming language (default: python).

    Returns:
        StyleResult with a 0-100 score and list of style violations.
    """
    # Real implementation would call ruff / pycodestyle / eslint etc.
    # For demo purposes we return a perfect score when not simulated.
    return StyleResult(score=100, violations=[])


SUGGEST_IMPROVEMENTS_EXAMPLES = [
    ExampleCall(
        id="basic-function",
        input='{"code": "def add(a, b):\\n    return a + b"}',
        output=(
            '{"suggestions": ["Add type annotations", "Add a docstring"],'
            ' "refactored_snippet": "def add(a: int, b: int) -> int:\\n    '
            "'''Return the sum of a and b.'''\\n    return a + b\"}"
        ),
    )
]


@traced(name="suggest_improvements", span_type="tool")
@mockable(example_calls=SUGGEST_IMPROVEMENTS_EXAMPLES)
async def suggest_improvements(code: str) -> ImprovementResult:
    """Analyse code and return actionable improvement suggestions.

    Args:
        code: Source code to analyse.

    Returns:
        ImprovementResult with suggestions and an optional refactored snippet.
    """
    # Real implementation would call an LLM or static analysis tool.
    return ImprovementResult(suggestions=[], refactored_snippet=code)


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------


@traced(name="main")
async def main(input: CodeReviewInput) -> CodeReviewOutput:
    """Orchestrate three code-review tools and produce a unified report.

    Each tool call creates its own OpenTelemetry span with span_type="tool",
    which enables trajectory-based evaluation and simulation.
    """
    syntax = await check_syntax(input.code, input.language)
    style = await check_style(input.code, input.language)
    improvements = await suggest_improvements(input.code)

    issues = len(syntax.errors) + len(style.violations)
    summary = (
        f"Found {issues} issue(s). "
        f"Style score: {style.score}/100. "
        f"{len(improvements.suggestions)} improvement suggestion(s)."
    )

    return CodeReviewOutput(
        syntax=syntax,
        style=style,
        improvements=improvements,
        summary=summary,
    )
