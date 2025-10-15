import enum

from ._console import ConsoleLogger

console = ConsoleLogger().get_instance()


class Resources(str, enum.Enum):
    """Available resources that can be created."""

    EVALUATOR = "evaluator"

    @classmethod
    def from_string(cls, resource: str) -> "Resources":  # type: ignore
        try:
            return Resources(resource)
        except ValueError:
            valid_resources = ", ".join([r.value for r in Resources])
            console.error(
                f"Invalid resource type: '{resource}'. Valid types are: {valid_resources}"
            )
