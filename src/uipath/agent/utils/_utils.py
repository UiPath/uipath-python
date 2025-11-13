import json
import logging
from pathlib import Path, PurePath
from typing import Any

from httpx import Response
from pydantic import TypeAdapter

from uipath._cli._utils._constants import (
    EVALS_DIRECTORY_NAME,
)
from uipath._cli._utils._eval_set import EvalHelpers
from uipath._cli._utils._project_files import pull_project  # type: ignore[attr-defined]
from uipath._cli._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    StudioSolutionsClient,
    resolve_path,
)
from uipath.agent.models.agent import (
    AgentDefinition,
)
from uipath.agent.models.evals import AgentEvalsDefinition

logger = logging.getLogger(__name__)


async def get_file(
    folder: ProjectFolder, path: PurePath, studio_client: StudioClient
) -> Response:
    resolved = resolve_path(folder, path)
    assert isinstance(resolved, ProjectFile), "Path file not found."
    return await studio_client.download_project_file_async(resolved)


async def create_agent_project(solution_id: str, project_name: str) -> str:
    studio_client = StudioSolutionsClient(solution_id=solution_id)
    project = await studio_client.create_project_async(project_name=project_name)
    return project["id"]


async def download_agent_project(
    project_id: str,
    target_project_dir: Path,
) -> None:
    """Downloads all project files to the target directory.

    Args:
        project_id: The project ID to download from
        target_project_dir: Directory where files will be downloaded
    """
    default_download_configuration = {
        None: target_project_dir,
    }

    logger.info(f"Downloading project {project_id}...")
    async for update in pull_project(project_id, default_download_configuration):
        logger.info(update.message)

    logger.info(f"Successfully downloaded project {project_id}.")


def load_agent_definition(
    target_project_dir: Path,
) -> AgentDefinition:
    """Loads agent definition from downloaded files and applies migrations.

    Args:
        target_project_dir: Directory containing the downloaded files

    Returns:
        AgentDefinition with migrations applied
    """
    # Load agent definition from downloaded files
    agent_definition_path = target_project_dir / "agent.json"

    agent: dict[str, Any] = {}
    with open(agent_definition_path) as f:
        agent = json.load(f)

    # Load resources from downloaded files
    resources = agent.get("resources", []) if "resources" in agent else []
    resources_dir = target_project_dir / "resources"
    if resources_dir.exists() and resources_dir.is_dir():
        for file_path in resources_dir.rglob("*.json"):
            try:
                with open(file_path) as f:
                    resources.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load resource from {file_path}: {e}")

    # Load evaluators from downloaded files
    evaluators = []
    evaluators_dir = target_project_dir / EVALS_DIRECTORY_NAME / "evaluators"
    if evaluators_dir.exists() and evaluators_dir.is_dir():
        for file_path in evaluators_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    evaluators.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load evaluator from {file_path}: {e}")
    else:
        logger.warning(
            "Unable to read evaluators from project. Defaulting to empty evaluators."
        )

    # Load evaluation sets from downloaded files
    evaluation_sets = []
    eval_sets_dir = target_project_dir / EVALS_DIRECTORY_NAME / "eval-sets"
    if eval_sets_dir.exists() and eval_sets_dir.is_dir():
        for file_path in eval_sets_dir.glob("*.json"):
            evaluation_set, _ = EvalHelpers.load_eval_set(str(file_path))
            evaluation_sets.append(evaluation_set)
    else:
        logger.warning(
            "Unable to read eval-sets from project. Defaulting to empty eval-sets."
        )

    # Construct agent definition dictionary
    agent_definition_dict = {
        "evaluators": evaluators,
        "evaluationSets": evaluation_sets,
        **agent,
        "resources": resources,  # This overrides agent["resources"] if it exists
    }

    # Validate and create AgentDefinition
    agent_definition = TypeAdapter(AgentEvalsDefinition).validate_python(
        agent_definition_dict
    )

    logger.info("Successfully loaded agent definition.")
    return agent_definition
