import logging
from dataclasses import dataclass

from uipath.platform import UiPath
from uipath.platform.orchestrator import AssetsService, AttachmentsService, BucketsService, FolderService, JobsService, McpService, ProcessesService, QueuesService
from uipath.platform.action_center import TasksService
from uipath.platform.connections import ConnectionsService
from uipath.platform.context_grounding import ContextGroundingService
from uipath.platform.chat import ConversationsService, UiPathVertexService, UiPathBedrockService, GeminiModels, BedrockModels, APIFlavor
from uipath.platform.documents import DocumentsService
from uipath.platform.entities import EntitiesService
from uipath.platform.resource_catalog import ResourceCatalogService

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


async def test_llm_vertex(sdk: UiPath):
    contents = [
        {
            "role": "user",
            "parts": [{"text": "What is the capital of France? Answer in one word."}]
        }
    ]

    result = await sdk.llm_vertex.generate_content(
        contents,
        model=GeminiModels.gemini_2_5_flash,
        generation_config={
            "temperature": 0.7,
            "maxOutputTokens": 100,
        }
    )
    logger.info("LLM Vertex Response: %s", result)


async def test_llm_bedrock(sdk: UiPath):
    messages = [
        {
            "role": "user",
            "content": [{"text": "What is the capital of France? Answer in one word."}]
        }
    ]

    result_converse = await sdk.llm_bedrock.converse(
        messages,
        model=BedrockModels.anthropic_claude_haiku_4_5,
        inference_config={
            "maxTokens": 100,
            "temperature": 0.7,
        }
    )
    logger.info("LLM Bedrock Converse Response: %s", result_converse)

    messages_invoke = [
        {
            "role": "user",
            "content": [{"text": "What is the capital of Germany? Answer in one word."}]
        }
    ]

    result_invoke = await sdk.llm_bedrock.converse(
        messages_invoke,
        model=BedrockModels.anthropic_claude_haiku_4_5,
        inference_config={
            "maxTokens": 100,
            "temperature": 0.7,
        },
        api_flavor=APIFlavor.AWS_BEDROCK_INVOKE,
    )
    logger.info("LLM Bedrock Invoke Response: %s", result_invoke)

async def test_imports(sdk: UiPath):
    logger.info("BucketsService imported: %s", BucketsService)
    logger.info("QueuesService imported: %s", QueuesService)
    logger.info("AssetsService imported: %s", AssetsService)
    logger.info("AttachmentsService imported: %s", AttachmentsService)
    logger.info("ConnectionsService imported: %s", ConnectionsService)
    logger.info("ContextGroundingService imported: %s", ContextGroundingService)
    logger.info("ConversationsService imported: %s", ConversationsService)
    logger.info("DocumentsService imported: %s", DocumentsService)
    logger.info("EntitiesService imported: %s", EntitiesService)
    logger.info("FolderService imported: %s", FolderService)
    logger.info("JobsService imported: %s", JobsService)
    logger.info("McpService imported: %s", McpService)
    logger.info("ProcessesService imported: %s", ProcessesService)
    logger.info("ResourceCatalogService imported: %s", ResourceCatalogService)
    logger.info("TasksService imported: %s", TasksService)
    logger.info("UiPathVertexService imported: %s", UiPathVertexService)
    logger.info("UiPathBedrockService imported: %s", UiPathBedrockService)
    logger.info("GeminiModels imported: %s", GeminiModels)
    logger.info("BedrockModels imported: %s", BedrockModels)
    logger.info("Imports test passed.")

@dataclass
class EchoIn:
    message: str


@dataclass
class EchoOut:
    message: str


async def main(input: EchoIn) -> EchoOut:
    sdk = UiPath()

    await test_llm(sdk)
    await test_llm_vertex(sdk)
    await test_llm_bedrock(sdk)
    await test_imports(sdk)

    return EchoOut(message=input.message)
