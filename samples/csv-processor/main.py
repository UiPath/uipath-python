import logging
import io
import pandas as pd

from uipath.platform import UiPath
from uipath.platform.attachments import Attachment
from pydantic import BaseModel
from uipath.platform.common import UiPathConfig
logger = logging.getLogger(__name__)

class Input(BaseModel):
    attachment: Attachment

async def main(input: Input) -> None:
    uipath = UiPath()
    async with uipath.attachments.open_async(attachment=input.attachment) as (attachment, response):
        async for raw_bytes in response.aiter_raw():
            df = pd.read_csv(io.BytesIO(raw_bytes))

            processing_output = f"CSV shape {df.shape}\n\nCSV columns {df.columns}"
            await uipath.jobs.create_attachment_async(
                name="processed_output.txt",
                content=str(processing_output),
                folder_key=UiPathConfig.folder_key,
                job_key=UiPathConfig.job_key,
            )
