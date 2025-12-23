from uipath.platform import UiPath
from uipath.platform.documents import ProjectType, ActionPriority

PROJECT_NAME = "TestIxpProject"
TAG = "live"
FILE_PATH = "test.pdf"
ACTION_TITLE = "Test IXP Validation Action"
ACTION_CATALOG = "default_du_actions"
ACTION_FOLDER = "Shared"
ACTION_PRIORITY = ActionPriority.MEDIUM
STORAGE_BUCKET_NAME = "du_storage_bucket"
STORAGE_BUCKET_DIRECTORY_PATH = "TestDirectory"


def extract_validate():
    uipath = UiPath()

    extraction_response = uipath.documents.extract(
        tag=TAG,
        project_name=PROJECT_NAME,
        project_type=ProjectType.IXP,
        file_path=FILE_PATH,
    )

    validation_action = uipath.documents.create_validate_extraction_action(
        action_title=ACTION_TITLE,
        action_priority=ACTION_PRIORITY,
        action_catalog=ACTION_CATALOG,
        action_folder=ACTION_FOLDER,
        storage_bucket_name=STORAGE_BUCKET_NAME,
        storage_bucket_directory_path=STORAGE_BUCKET_DIRECTORY_PATH,
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=validation_action
    )
