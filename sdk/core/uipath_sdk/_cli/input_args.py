import ast
from typing import Any, Dict, Optional

TYPE_MAP = {
    "int": "integer",
    "float": "double",
    "str": "string",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "Optional": "object",
}


class ArgumentVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.input_state: Dict[str, Dict[str, Any]] = {}
        self.output_state: Dict[str, Dict[str, Any]] = {}
        self.current_class: Optional[str] = None
        self.has_arg: bool = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.current_class = node.name
        self.has_arg = False

        # Visit all class members first to check for Arguments
        self.generic_visit(node)

        # Only add class to state if it had an Argument
        if self.has_arg:
            self.input_state["state"] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            self.output_state["state"] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            # Re-visit to actually process the members
            self.generic_visit(node)

        self.current_class = None
        self.has_arg = False

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self.current_class:
            return

        if not isinstance(node.target, ast.Name):
            return

        # Look for Argument annotation
        if isinstance(node.annotation, ast.Subscript):
            if (
                isinstance(node.annotation.value, ast.Name)
                and node.annotation.value.id == "Annotated"
            ):
                args = node.annotation.slice
                if isinstance(args, ast.Tuple):
                    base_type = args.elts[0]
                    field_name = node.target.id
                    field_type = self.resolve_type(base_type)

                    # Check if type is Optional
                    is_optional = (
                        isinstance(base_type, ast.Subscript)
                        and isinstance(base_type.value, ast.Name)
                        and base_type.value.id == "Optional"
                    )

                    # Extract default value if present
                    default_value = None
                    if node.value:
                        if isinstance(node.value, ast.Constant):
                            default_value = node.value.value
                        elif isinstance(node.value, ast.List):
                            default_value = []
                        elif isinstance(node.value, ast.Dict):
                            default_value = {}

                    for decorator in args.elts[1:]:
                        if isinstance(decorator, ast.Call) and isinstance(
                            decorator.func, ast.Name
                        ):
                            if decorator.func.id == "InputArgument":
                                self.has_arg = True
                                if "state" in self.input_state:
                                    schema = self.input_state["state"]
                                    field_schema = {"type": field_type}
                                    if default_value is not None:
                                        field_schema["default"] = default_value
                                    schema["properties"][field_name] = field_schema
                                    if not is_optional:
                                        schema["required"].append(field_name)
                            elif decorator.func.id == "OutputArgument":
                                self.has_arg = True
                                if "state" in self.output_state:
                                    schema = self.output_state["state"]
                                    field_schema = {"type": field_type}
                                    if default_value is not None:
                                        field_schema["default"] = default_value
                                    schema["properties"][field_name] = field_schema
                                    if not is_optional:
                                        schema["required"].append(field_name)

    def resolve_type(self, annotation: ast.AST) -> str:
        if isinstance(annotation, ast.Name):
            return TYPE_MAP.get(annotation.id, "object")
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                base = annotation.value.id
                if base in ("List", "list"):
                    return "array"
                if base in ("Dict", "dict"):
                    return "object"
                if base == "Optional":
                    return self.resolve_type(annotation.slice)
        return "object"


def generate_args(path: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Parse Python file at given path and extract input/output arguments schema.

    Args:
        path: Path to Python file to parse

    Returns:
        Dictionary with 'input' and 'output' keys mapping class names to their argument schemas
    """
    with open(path, "r") as f:
        tree = ast.parse(f.read(), filename=path)

    visitor = ArgumentVisitor()
    visitor.visit(tree)

    return {"input": visitor.input_state, "output": visitor.output_state}
