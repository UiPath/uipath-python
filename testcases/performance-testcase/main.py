import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class EchoIn:
    message: str
    repeat: int | None = 1
    prefix: str | None = None


@dataclass
class EchoOut:
    message: str


def main(input: EchoIn) -> EchoOut:
    # Record start time
    start_time = time.perf_counter()

    result = []

    for _ in range(input.repeat):
        line = input.message
        if input.prefix:
            line = f"{input.prefix}: {line}"
        result.append(line)

    # Record end time
    end_time = time.perf_counter()
    user_code_time = end_time - start_time

    # Write timing to file for later collection
    timing_file = Path("artifacts/user_code_timing.json")
    timing_file.parent.mkdir(parents=True, exist_ok=True)
    timing_file.write_text(json.dumps({
        "user_code_time_seconds": user_code_time,
        "start_time": start_time,
        "end_time": end_time
    }))

    return EchoOut(message="\n".join(result))
