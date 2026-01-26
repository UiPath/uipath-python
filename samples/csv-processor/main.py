import io
import logging
import os

import pandas as pd
from pydantic import BaseModel

from uipath.platform import UiPath
from uipath.platform.attachments import Attachment
from uipath.platform.common import UiPathConfig

logger = logging.getLogger(__name__)


class Input(BaseModel):
    attachment: Attachment


class Output(BaseModel):
    processing_output: str


async def main(input: Input) -> Output:
    # Check if full_name points to a local file (for testing)
    attachment_path = input.attachment.full_name

    if os.path.exists(attachment_path):
        # Local file mode for testing
        logger.info(f"Reading local file: {attachment_path}")
        with open(attachment_path, "rb") as f:
            df = pd.read_csv(io.BytesIO(f.read()))
            processing_output = (
                f"CSV shape {df.shape}\n\nCSV columns {df.columns.tolist()}"
            )
            logger.info(f"Processed CSV: {processing_output}")
            print(processing_output)
            return Output(processing_output=processing_output)
    else:
        # Platform mode - use attachment API
        uipath = UiPath()
        async with uipath.attachments.open_async(attachment=input.attachment) as (
            attachment,
            response,
        ):
            async for raw_bytes in response.aiter_raw():
                df = pd.read_csv(io.BytesIO(raw_bytes))

                processing_output = (
                    f"CSV shape {df.shape}\n\nCSV columns {df.columns.tolist()}"
                )
                await uipath.jobs.create_attachment_async(
                    name="processed_output.txt",
                    content=str(processing_output),
                    folder_key=UiPathConfig.folder_key,
                    job_key=UiPathConfig.job_key,
                )
                return Output(processing_output=processing_output)
