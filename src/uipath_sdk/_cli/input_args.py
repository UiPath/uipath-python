import ast
from typing import Any

TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


class TypedDictTransformer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.schemas: dict[str, dict[str, Any]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if any(self.is_typed_dict_base(base) for base in node.bases):
            schema: dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ):
                    field = stmt.target.id
                    field_type = self.resolve_type(stmt.annotation)
                    if "properties" not in schema:
                        schema["properties"] = {}
                    schema["properties"][field] = {"type": field_type}

                    if "required" not in schema:
                        schema["required"] = []
                    schema["required"].append(field)
            self.schemas[node.name.lower()] = schema
        self.generic_visit(node)

    def is_typed_dict_base(self, base: ast.AST) -> bool:
        if isinstance(base, ast.Name) and base.id == "TypedDict":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "TypedDict":
            return True
        return False

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
        return "object"


# if __name__ == "__main__":
#     if len(sys.argv) != 3:
#         print("Usage: python transform.py <input.py> <output.json>")
#         sys.exit(1)

#     input_path, output_path = sys.argv[1], sys.argv[2]
#     with open(input_path, "r") as f:
#         tree = ast.parse(f.read(), filename=input_path)

#     transformer = TypedDictTransformer()
#     transformer.visit(tree)

#     with open(output_path, "w") as f:
#         json.dump(transformer.schemas, f, indent=2)


def generate_input_args(path: str) -> dict[str, dict[str, Any]]:
    with open(path, "r") as f:
        tree = ast.parse(f.read(), filename=path)

    transformer = TypedDictTransformer()
    transformer.visit(tree)

    return transformer.schemas
