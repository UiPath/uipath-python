from uipath import UiPath
from uipath.models.documents import ProjectType, ActionPriority

def extract_validate():
    uipath = UiPath()

    extraction_response = uipath.documents.extract(
        tag="live",
        project_name="TestIxpProject",
        project_type=ProjectType.IXP,
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
