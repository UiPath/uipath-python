import logging
from dataclasses import dataclass
from typing import Optional

from uipath import UiPath

logger = logging.getLogger(__name__)

sdk = None


def test_assets(sdk: UiPath):
    sdk.assets.retrieve(name="MyAsset")


async def test_llm(sdk: UiPath):
    messages = [
        {"role": "system", "content": "You are a helpful programming assistant."},
        {"role": "user", "content": "How do I read a file in Python?"},
        {"role": "assistant", "content": "You can use the built-in open() function."},
        {"role": "user", "content": "Can you show an example?"},
    ]

    result_openai = await sdk.llm_openai.chat_completions(messages)
    logger.info("LLM OpenAI Response: %s", result_openai.choices[0].message.content)

    result_normalized = await sdk.llm.chat_completions(messages)
    logger.info(
        "LLM Normalized Response: %s", result_normalized.choices[0].message.content
    )


@dataclass
class EchoIn:
    message: str


@dataclass
class EchoOut:
    message: str


async def main(input: EchoIn) -> EchoOut:
    sdk = UiPath()

    await test_llm(sdk)
    return EchoOut(message=input.message)
