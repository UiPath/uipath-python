import logging
from dataclasses import dataclass

from uipath.platform import UiPath
from uipath.platform.orchestrator import AssetsService, AttachmentsService, BucketsService, FolderService, JobsService, McpService, ProcessesService, QueuesService
from uipath.platform.action_center import TasksService
from uipath.platform.connections import ConnectionsService
from uipath.platform.context_grounding import ContextGroundingService
from uipath.platform.chat import ConversationsService
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
    await test_imports(sdk)

    return EchoOut(message=input.message)
