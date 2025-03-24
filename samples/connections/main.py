from dataclasses import dataclass
import io
import os
import dotenv
from typing import Optional
from uipath_sdk import UiPathSDK
from uipath_connectors.uipath_airdk import (
    WebSearchRequest,
    GenerateEmailRequest,
    WebSearchRequestSearchEngine,
)
from uipath_connectors.google_gmail import (
    SendEmailBody,
    SendEmailRequest,
)
from uipath_connectors.google_gmail.types import File as EmailAttachmentFile

dotenv.load_dotenv()

@dataclass
class EchoIn:
    message: str
    debug: Optional[bool] = False
    send_email_to: Optional[bool] = None

@dataclass
class EchoOut:
    message: str


def main(input: EchoIn) -> EchoOut:
    sdk = UiPathSDK()
    airdk = sdk.connections.uipath_airdk(os.environ["UIPATH_AIRDK_CONNECTION_KEY"])

    initialSearch = airdk.web_search(body=WebSearchRequest(provider=WebSearchRequestSearchEngine.GOOGLECUSTOMSEARCH, query=input.message))
    if input.debug:
        print(initialSearch.model_dump_json(indent=4))

    content = airdk.generate_email(body=GenerateEmailRequest(
        need_salutation=True,
        need_sign_off=True,
        email_content="Generate a 10 paragraph summary of the following web search results: " + initialSearch.model_dump_json(),
        ))
    if input.debug:
        print(content.model_dump_json(indent=4))

    if input.send_email_to:
        gmail = sdk.connections.google_gmail(os.environ["UIPATH_GOOGLE_GMAIL_CONNECTION_KEY"])
        gmail.client._client.verify = False
        if input.debug:
            print(content.emailContent)

        send_email = gmail.send_email(
            body=SendEmailBody(
                body=SendEmailRequest(
                    to=input.send_email_to,
                    body= content.emailContent,
                    subject="Email from the research",
                ),
                file=EmailAttachmentFile(
                    payload=io.BytesIO(initialSearch.model_dump_json(indent=4).encode('utf-8')),
                    file_name="search.json",
                    content_type="application/json",
                ),
            )
        )
        if input.debug:
            print(send_email.model_dump_json(indent=4))

    return EchoOut(message=content.model_dump_json(indent=4))

if __name__ == "__main__":
    main(EchoIn(message="What is the capital of France?", debug=True, send_email_to="alice.roprau@gmail.com"))
