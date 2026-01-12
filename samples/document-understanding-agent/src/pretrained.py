from uipath.platform import UiPath
from uipath.platform.documents import ProjectType, ActionPriority

DOCUMENT_TYPE_NAME = "invoices"
FILE_PATH = "test.pdf"
ACTION_TITLE = "Test Validation Action"
ACTION_PRIORITY = ActionPriority.MEDIUM
ACTION_CATALOG = "default_du_actions"
ACTION_FOLDER = "Shared"
STORAGE_BUCKET_NAME = "du_storage_bucket"
STORAGE_BUCKET_DIRECTORY_PATH = "TestDirectory"

def extract_validate():
    uipath = UiPath()

    extraction_response = uipath.documents.extract(
        project_type=ProjectType.PRETRAINED,
        document_type_name=DOCUMENT_TYPE_NAME,
        file_path=FILE_PATH,
    )

    extraction_action = uipath.documents.create_validate_extraction_action(
        action_title=ACTION_TITLE,
        action_priority=ACTION_PRIORITY,
        action_catalog=ACTION_CATALOG,
        action_folder=ACTION_FOLDER,
        storage_bucket_name=STORAGE_BUCKET_NAME,
        storage_bucket_directory_path=STORAGE_BUCKET_DIRECTORY_PATH,
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=extraction_action
    )

def classify_extract_validate():
    uipath = UiPath()

    classification_results = uipath.documents.classify(
        project_type=ProjectType.PRETRAINED, file_path=FILE_PATH
    )

    best_confidence_result = max(classification_results, key=lambda result: result.confidence)

    extraction_response = uipath.documents.extract(
        classification_result=best_confidence_result
    )

    extraction_action = uipath.documents.create_validate_extraction_action(
        action_title=ACTION_TITLE,
        action_priority=ACTION_PRIORITY,
        action_catalog=ACTION_CATALOG,
        action_folder=ACTION_FOLDER,
        storage_bucket_name=STORAGE_BUCKET_NAME,
        storage_bucket_directory_path=STORAGE_BUCKET_DIRECTORY_PATH,
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=extraction_action
    )