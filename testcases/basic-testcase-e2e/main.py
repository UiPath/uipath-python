import logging
import os
from dataclasses import dataclass
from typing import Optional
from contextlib import suppress
from uipath.tracing import traced 
from opentelemetry import trace
from uipath import UiPath

tracer = trace.get_tracer(__name__)

logger = logging.getLogger(__name__)

@traced()
def print_env_vars():
    for key, value in os.environ.items():
        print(f"{key}={value}")

@traced()
def test_function():
    return "test_output"


@dataclass
class EchoIn:
    message: str
    repeat: Optional[int] = 1
    prefix: Optional[str] = None


@dataclass
class EchoOut:
    message: str


def main(input: EchoIn) -> EchoOut:
    print_env_vars()

    logger.info("Starting UiPath SDK agent...")

    uipath = UiPath()

    with tracer.start_as_current_span("foo") as span:
        with tracer.start_as_current_span("bar") as span2:
            test_function()

    with suppress(Exception): 
        uipath.buckets.upload(name="test-bucket", blob_file_path="test.txt", content_type="text/plain", content="Hello, World!")
    
    with suppress(Exception): 
        items = uipath.queues.list_items()

    result = []

    for _ in range(input.repeat):
        line = input.message
        if input.prefix:
            line = f"{input.prefix}: {line}"
        result.append(line)

    logger.info("UiPath SDK ended successfully.")

    return EchoOut(message="\n".join(result))
