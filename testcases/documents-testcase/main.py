from dataclasses import dataclass
from typing import Optional

from uipath import UiPath
from uipath.models.documents import ProjectType, ActionPriority
import os


@dataclass
class EchoIn:
    message: str
    repeat: Optional[int] = 1
    prefix: Optional[str] = None


@dataclass
class EchoOut:
    message: str

def test_extract_ixp(uipath: UiPath):
    os.makedirs("results", exist_ok=True)

    import jwt
    test = jwt.decode(uipath._config.secret, options={"verify_signature": False}  )
    raise Exception(test["aud"] + " " + test["scope"])

    extraction_response = uipath.documents.extract(
        tag="live",
        project_name="E2E Tests",
        project_type=ProjectType.IXP,
        file_path="test_data/uber_receipt.pdf",
    )

    with open("results/extraction_response.json", "w") as f:
        f.write(extraction_response.model_dump_json())

    validation_action = uipath.documents.create_validate_extraction_action(
        action_title="Test Validation Action",
        action_priority=ActionPriority.MEDIUM,
        action_catalog="default_du_actions",
        action_folder="Shared",
        storage_bucket_name="du_storage_bucket",
        storage_bucket_directory_path="TestDirectory",
        extraction_response=extraction_response,
    )

    with open("results/validation_action.json", "w") as f:
        f.write(validation_action.model_dump_json())


def main(input: EchoIn) -> EchoOut:
    uipath = UiPath()

    test_extract_ixp(uipath)

    return EchoOut(message=input.message)