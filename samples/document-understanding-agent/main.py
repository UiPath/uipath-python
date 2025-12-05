from dataclasses import dataclass
from src import ixp, du_modern, pretrained


@dataclass
class EchoIn:
    message: str


@dataclass
class EchoOut:
    message: str

def main(input: EchoIn) -> EchoOut:
    ixp.extract_validate()

    du_modern.extract_validate()
    du_modern.classify_extract_validate()

    pretrained.extract_validate()
    pretrained.classify_extract_validate()

    return EchoOut(message="")
