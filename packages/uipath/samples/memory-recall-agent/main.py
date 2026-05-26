"""Coded agent sample that recalls context from a UiPath Memory Space."""

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

from uipath.platform import UiPath
from uipath.platform.memory import (
    MemorySearchRequest,
    MemorySearchResponse,
    SearchField,
    SearchMode,
    SearchSettings,
)
from uipath.tracing import traced

DEFAULT_MEMORY_SPACE_NAME = "support-agent-memory"
DEFAULT_FOLDER_PATH = "Shared"
BASE_SYSTEM_PROMPT = (
    "You are a support triage agent. Use recalled memory when it is relevant. "
    "If the recalled memory does not answer the question, say what is missing."
)


@dataclass
class MemoryAgentInput:
    """Input for the memory recall sample."""

    question: str
    memory_space_id: str | None = None
    memory_space_name: str | None = DEFAULT_MEMORY_SPACE_NAME
    folder_path: str | None = DEFAULT_FOLDER_PATH
    result_count: int = 3
    threshold: float = 0.0
    search_mode: str = SearchMode.Hybrid.value
    create_if_missing: bool = False
    generate_answer: bool = True


class MemoryHitField(BaseModel):
    """A field from a memory search match."""

    key_path: list[str]
    value: str
    score: float
    weighted_score: float


class MemoryHit(BaseModel):
    """A simplified memory search match for agent output."""

    memory_item_id: str
    score: float
    semantic_score: float
    weighted_score: float
    fields: list[MemoryHitField] = Field(default_factory=list)


class MemoryAgentOutput(BaseModel):
    """Output from the memory recall sample."""

    answer: str
    memory_space_id: str
    memory_space_name: str | None = None
    system_prompt_injection: str = ""
    matches: list[MemoryHit] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _coerce_search_mode(value: str) -> SearchMode:
    for mode in SearchMode:
        if value.lower() == mode.value.lower():
            return mode

    valid_modes = ", ".join(mode.value for mode in SearchMode)
    raise ValueError(f"search_mode must be one of: {valid_modes}")


def _clamp_search_settings(input: MemoryAgentInput) -> tuple[int, float]:
    result_count = min(max(input.result_count, 1), 10)
    threshold = min(max(input.threshold, 0.0), 1.0)
    return result_count, threshold


async def _resolve_memory_space(
    sdk: UiPath,
    input: MemoryAgentInput,
) -> tuple[str, str | None]:
    memory_space_id = _optional_text(input.memory_space_id)
    if memory_space_id:
        return memory_space_id, _optional_text(input.memory_space_name)

    memory_space_name = _optional_text(input.memory_space_name)
    if memory_space_name is None:
        raise ValueError(
            "Either memory_space_id or memory_space_name must be provided."
        )

    folder_path = _optional_text(input.folder_path)
    filter_expression = f"Name eq '{_escape_odata_string(memory_space_name)}'"
    spaces = await sdk.memory.list_async(
        filter=filter_expression,
        top=1,
        folder_path=folder_path,
    )

    if spaces.value:
        memory_space = spaces.value[0]
        return memory_space.id, memory_space.name

    if input.create_if_missing:
        memory_space = await sdk.memory.create_async(
            name=memory_space_name,
            description="Memory space created by the memory recall sample.",
            folder_path=folder_path,
        )
        return memory_space.id, memory_space.name

    raise ValueError(
        f"Memory space '{memory_space_name}' was not found. "
        "Pass memory_space_id directly or set create_if_missing to true."
    )


def _build_search_request(input: MemoryAgentInput) -> MemorySearchRequest:
    result_count, threshold = _clamp_search_settings(input)

    return MemorySearchRequest(
        fields=[
            SearchField(
                key_path=["input"],
                value=input.question,
            )
        ],
        settings=SearchSettings(
            threshold=threshold,
            result_count=result_count,
            search_mode=_coerce_search_mode(input.search_mode),
        ),
        definition_system_prompt=BASE_SYSTEM_PROMPT,
    )


def _to_memory_hits(response: MemorySearchResponse) -> list[MemoryHit]:
    return [
        MemoryHit(
            memory_item_id=match.memory_item_id,
            score=match.score,
            semantic_score=match.semantic_score,
            weighted_score=match.weighted_score,
            fields=[
                MemoryHitField(
                    key_path=field.key_path,
                    value=field.value,
                    score=field.score,
                    weighted_score=field.weighted_score,
                )
                for field in match.fields
            ],
        )
        for match in response.results
    ]


def _fallback_answer(response: MemorySearchResponse) -> str:
    if response.results:
        return (
            f"Found {len(response.results)} relevant memory item(s). "
            "Set generate_answer to true to turn the recalled context into a response."
        )

    return "No matching memories were found for this question."


async def _generate_answer(
    sdk: UiPath,
    input: MemoryAgentInput,
    response: MemorySearchResponse,
) -> str:
    if not response.results and not response.system_prompt_injection:
        return _fallback_answer(response)

    system_prompt = BASE_SYSTEM_PROMPT
    if response.system_prompt_injection:
        system_prompt = f"{system_prompt}\n\n{response.system_prompt_injection}"

    completion = await sdk.llm.chat_completions(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input.question},
        ],
        temperature=0,
        max_tokens=700,
    )

    if not completion.choices:
        return _fallback_answer(response)

    return completion.choices[0].message.content or _fallback_answer(response)


@traced(name="memory_recall_agent")
async def main(input: MemoryAgentInput) -> MemoryAgentOutput:
    """Search a UiPath Memory Space and optionally answer with recalled context."""
    sdk = UiPath()
    memory_space_id, memory_space_name = await _resolve_memory_space(sdk, input)
    search_response = await sdk.memory.search_async(
        memory_space_id=memory_space_id,
        request=_build_search_request(input),
        folder_path=_optional_text(input.folder_path),
    )

    if input.generate_answer:
        answer = await _generate_answer(sdk, input, search_response)
    else:
        answer = _fallback_answer(search_response)

    return MemoryAgentOutput(
        answer=answer,
        memory_space_id=memory_space_id,
        memory_space_name=memory_space_name,
        system_prompt_injection=search_response.system_prompt_injection,
        matches=_to_memory_hits(search_response),
        metadata=search_response.metadata,
    )
