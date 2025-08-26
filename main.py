from dataclasses import dataclass
from typing import Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer("uipath-dev-terminal")


@dataclass
class EchoIn:
    message: str
    repeat: Optional[int] = 1
    prefix: Optional[str] = None


@dataclass
class EchoOut:
    message: str


def main(input: EchoIn) -> EchoOut:
    result = []
    print("starting echo function")
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("key", "value")
        span.add_event("Something happened")

        try:
            for _ in range(input.repeat or 1):
                with tracer.start_as_current_span("inner-operation") as inner_span:
                    inner_span.set_attribute("key2", "value2")
                    line = input.message
                    if input.prefix:
                        line = f"{input.prefix}: {line}"
                    result.append(line)
            span.set_status(StatusCode.OK)
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise

    print("after echo function")
    return EchoOut(message="\n".join(result))
