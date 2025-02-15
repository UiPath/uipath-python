import ast
from typing import Any, Dict, List, Optional, TypedDict, Union


class PropertySchema(TypedDict, total=False):
    type: str
    items: Dict[str, Any]
    default: Union[str, int, float, bool, List[Any], Dict[str, Any]]


class ArgumentSchema(TypedDict):
    type: str
    properties: Dict[str, PropertySchema]
    required: List[str]


TYPE_MAP: Dict[str, str] = {
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
        self.input_schema: ArgumentSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        self.output_schema: ArgumentSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self.current_class or not isinstance(node.target, ast.Name):
            return

        field_name = node.target.id

        if isinstance(node.annotation, ast.Subscript):
            if (
                isinstance(node.annotation.value, ast.Name)
                and node.annotation.value.id == "Annotated"
            ):
                args = node.annotation.slice
                if isinstance(args, ast.Tuple):
                    base_type = args.elts[0]
                    is_optional = self.is_optional_type(base_type)
                    field_schema = self.get_field_schema(base_type, node.value)

                    for decorator in args.elts[1:]:
                        if isinstance(decorator, ast.Call) and isinstance(
                            decorator.func, ast.Name
                        ):
                            if decorator.func.id == "InputArgument":
                                self.input_schema["properties"][field_name] = (
                                    field_schema
                                )
                                if not is_optional:
                                    self.input_schema["required"].append(field_name)

                            if decorator.func.id == "OutputArgument":
                                self.output_schema["properties"][field_name] = (
                                    field_schema
                                )
                                if not is_optional:
                                    self.output_schema["required"].append(field_name)

    def get_field_schema(
        self, type_node: ast.AST, default_value: Optional[ast.AST] = None
    ) -> PropertySchema:
        """Generate complete schema for a field based on its type and default value."""
        schema: PropertySchema = {"type": "object"}

        if isinstance(type_node, ast.Name):
            schema["type"] = TYPE_MAP.get(type_node.id, "object")

        elif isinstance(type_node, ast.Subscript):
            if isinstance(type_node.value, ast.Name):
                base = type_node.value.id
                if base == "Optional":
                    inner_schema = self.get_field_schema(type_node.slice)
                    schema = inner_schema
                elif base in ("List", "list"):
                    items_schema = self.get_field_schema(type_node.slice)
                    schema = {"type": "array", "items": items_schema}
                elif base in ("Dict", "dict"):
                    schema = {"type": "object"}

        if default_value is not None:
            if isinstance(default_value, ast.Constant):
                schema["default"] = default_value.value
            elif isinstance(default_value, ast.List):
                schema["default"] = []
            elif isinstance(default_value, ast.Dict):
                schema["default"] = {}

        return schema

    def is_optional_type(self, node: ast.AST) -> bool:
        """Check if a type annotation represents an Optional type."""
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Optional"
        )


def generate_args(path: str) -> Dict[str, ArgumentSchema]:
    """
    Parse Python file at given path and extract input/output arguments schema.

    Args:
        path: Path to Python file to parse

    Returns:
        Dictionary with 'input' and 'output' keys containing argument schemas
    """
    with open(path, "r") as f:
        tree = ast.parse(f.read(), filename=path)

    visitor = ArgumentVisitor()
    visitor.visit(tree)

    return {"input": visitor.input_schema, "output": visitor.output_schema}
