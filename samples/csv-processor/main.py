import logging
import io
import pandas as pd

from uipath._services.attachments_service import AttachmentMode
from uipath.platform import UiPath
from uipath.platform.attachments import Attachment

logger = logging.getLogger(__name__)

async def main(input: Attachment) -> Attachment:
    uipath = UiPath()
    async with uipath.attachments.open_async(attachment=input) as (attachment, response):
        async for raw_bytes in response.aiter_raw():
            df = pd.read_csv(io.BytesIO(raw_bytes))

            processing_output = f"CSV shape {df.shape}\n\nCSV columns {df.columns}"
            async with uipath.attachments.open_async(
                attachment=Attachment(
                    FullName="CSVSummary.txt",
                    MimeType="text/plain",
                ),
                mode=AttachmentMode.WRITE,
                content=processing_output,
            ) as (uploaded_attachment, upload_response):
                return uploaded_attachment
