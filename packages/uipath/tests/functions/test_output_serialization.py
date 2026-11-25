"""A function's output is serialized under the keys its output schema declares."""

import uuid

from pydantic import BaseModel

from uipath.functions.type_conversion import convert_from_class
from uipath.platform.attachments import Attachment


class Output(BaseModel):
    file: Attachment


def test_aliased_fields_are_serialized_by_alias():
    attachment_id = uuid.uuid4()
    output = Output(
        file=Attachment(
            id=attachment_id, full_name="report.md", mime_type="text/markdown"
        )
    )

    assert convert_from_class(output) == {
        "file": {
            "ID": attachment_id,
            "FullName": "report.md",
            "MimeType": "text/markdown",
            "Metadata": None,
        }
    }


def test_models_without_aliases_are_unchanged():
    class Plain(BaseModel):
        summary: str

    assert convert_from_class(Plain(summary="ok")) == {"summary": "ok"}
