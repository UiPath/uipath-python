import logging
from uipath.platform import UiPath
from uipath.platform.attachments import Attachment

logger = logging.getLogger(__name__)

async def main(input: Attachment) -> None:
    uipath = UiPath()
    # Option 1: Download
    uipath.attachments.open(key=input.file.id, destination_path=input.file.full_name)

    # Option 2: Access Stream
    with open(input.full_name, "wb") as wf:
        with uipath.attachments.open(attachment=input) as response:
            for raw_bytes in response.iter_raw():
                wf.write(raw_bytes)
