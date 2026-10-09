"""Memory-aware coded agent.

Searches a UiPath Agent Memory space for prior interactions relevant to
the user's query, stitches the LLMOps-rendered few-shot injection into
the LLM system prompt, then calls the UiPath LLM Gateway.

Required environment variables:
    UIPATH_URL            UiPath base URL (e.g. https://cloud.uipath.com/org/tenant)
    UIPATH_ACCESS_TOKEN   Personal access token or service token
    UIPATH_FOLDER_KEY     Folder that owns the memory space (or pass folder_path)

The memory space itself is created out-of-band (UI, CLI, or
``uipath.memory.create``) and its id is passed in via ``AgentInput``.
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from uipath.platform import UiPath
from uipath.platform.chat import ChatModels
from uipath.platform.memory import (
    MemorySearchRequest,
    SearchField,
    SearchMode,
    SearchSettings,
)
from uipath.tracing import traced

load_dotenv()

BASE_SYSTEM_PROMPT = "You answer questions concisely and accurately."


class AgentInput(BaseModel):
    """Input model for the memory-aware agent."""

    query: str = Field(description="User question")
    memory_space_id: str = Field(
        description="ID of the memory space to recall from (folder-scoped)"
    )


class AgentOutput(BaseModel):
    """Output model for the memory-aware agent."""

    response: str = Field(description="Final LLM answer")
    matched_memories: int = Field(
        default=0, description="Number of memories returned by the search"
    )
    system_prompt_injection: str = Field(
        default="", description="The few-shot block stitched into the system prompt"
    )


@traced()
async def main(input: AgentInput) -> AgentOutput:
    """Recall memories, augment the system prompt, then call the LLM."""
    base_url = os.environ.get("UIPATH_URL")
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN")
    folder_key = os.environ.get("UIPATH_FOLDER_KEY")

    if not base_url or not access_token:
        return AgentOutput(
            response=(
                "Missing required environment variables. "
                "Set UIPATH_URL and UIPATH_ACCESS_TOKEN."
            ),
        )

    sdk = UiPath()

    # 1. Recall relevant prior interactions for this query.
    search_req = MemorySearchRequest(
        fields=[SearchField(key_path=["query"], value=input.query)],
        settings=SearchSettings(
            threshold=0.5,
            result_count=3,
            search_mode=SearchMode.Hybrid,
        ),
        definition_system_prompt=BASE_SYSTEM_PROMPT,
    )
    recall = await sdk.memory.search_async(
        memory_space_id=input.memory_space_id,
        request=search_req,
        folder_key=folder_key,
    )

    # 2. Stitch the LLMOps-rendered few-shot injection into the system prompt.
    system_prompt = BASE_SYSTEM_PROMPT
    if recall.system_prompt_injection:
        system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{recall.system_prompt_injection}"

    # 3. Call the LLM with the augmented system prompt.
    chat = await sdk.llm.chat_completions(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input.query},
        ],
        model=ChatModels.gpt_4_1_mini_2025_04_14,
        max_tokens=400,
        temperature=0.2,
    )

    answer = chat.choices[0].message.content or ""
    return AgentOutput(
        response=answer,
        matched_memories=len(recall.results),
        system_prompt_injection=recall.system_prompt_injection,
    )
