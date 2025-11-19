from uipath import UiPath
from uipath.models.documents import ProjectType, ActionPriority

TAG = "Production"
PROJECT_NAME = "TestModernProject"

def extract_validate():
    uipath = UiPath()

    extraction_response = uipath.documents.extract(
        tag=TAG,
        project_name=PROJECT_NAME,
        project_type=ProjectType.MODERN,
        document_type_name="TestDocumentType",
        file_path="test.pdf",
    )

    validation_action = uipath.documents.create_validate_extraction_action(
        action_title="Test Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=validation_action
    )

def classify_extract_validate():
    uipath = UiPath()

    classification_results = uipath.documents.classify(
        tag=TAG,
        project_name=PROJECT_NAME,
        project_type=ProjectType.MODERN,
        file_path="test.pdf",
    )

    validation_action = uipath.documents.create_validate_classification_action(
        action_title="Test Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        classification_results=classification_results,
    )

    validated_classification_results = uipath.documents.get_validate_classification_result(
        validation_action=validation_action
    )

    best_confidence_result = max(validated_classification_results, key=lambda result: result.confidence)

    extraction_response = uipath.documents.extract(classification_result=best_confidence_result)

    validation_action = uipath.documents.create_validate_extraction_action(
        action_title="Test Extraction Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=validation_action
    )

