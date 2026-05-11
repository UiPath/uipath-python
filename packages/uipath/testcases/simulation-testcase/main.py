from pydantic import BaseModel

from uipath.eval.mocks import mockable
from uipath.tracing import traced


class CodeReviewInput(BaseModel):
    code: str
    language: str = "python"


class SyntaxResult(BaseModel):
    valid: bool
    errors: list[str] = []


class StyleResult(BaseModel):
    score: int
    violations: list[str] = []


class ImprovementResult(BaseModel):
    suggestions: list[str] = []
    refactored_snippet: str = ""


class CodeReviewOutput(BaseModel):
    syntax: SyntaxResult
    style: StyleResult
    improvements: ImprovementResult
    summary: str


@mockable()
async def check_syntax(code: str, language: str = "python") -> SyntaxResult:
    """Check code for syntax errors."""
    if language != "python":
        return SyntaxResult(valid=True)
    try:
        compile(code, "<string>", "exec")
        return SyntaxResult(valid=True)
    except SyntaxError as exc:
        return SyntaxResult(valid=False, errors=[str(exc)])


@mockable()
async def check_style(code: str, language: str = "python") -> StyleResult:
    """Run style checks on the provided code."""
    return StyleResult(score=100, violations=[])


@mockable()
async def suggest_improvements(code: str) -> ImprovementResult:
    """Analyse code and return actionable improvement suggestions."""
    return ImprovementResult(suggestions=[], refactored_snippet=code)


@traced(name="main")
async def main(input: CodeReviewInput) -> CodeReviewOutput:
    """Orchestrate three code-review tools and produce a unified report."""
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
