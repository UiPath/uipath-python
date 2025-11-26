from uipath import UiPath
from uipath.models.documents import ProjectType, ActionPriority

def extract_validate():
    uipath = UiPath()

    extraction_response = uipath.documents.extract(
        project_type=ProjectType.PRETRAINED,
        document_type_name="invoices",
        file_path="test.pdf",
    )

    extraction_action = uipath.documents.create_validate_extraction_action(
        action_title="Test Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=extraction_action
    )

def classify_extract_validate():
    uipath = UiPath()

    classification_results = uipath.documents.classify(
        project_type=ProjectType.PRETRAINED, file_path="test.pdf"
    )

    best_confidence_result = max(classification_results, key=lambda result: result.confidence)

    extraction_response = uipath.documents.extract(
        classification_result=best_confidence_result
    )

    extraction_action = uipath.documents.create_validate_extraction_action(
        action_title="Test Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        extraction_response=extraction_response,
    )

    uipath.documents.get_validate_extraction_result(
        validation_action=extraction_action
    )