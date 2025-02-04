import importlib.util
import inspect
import sys
from dataclasses import fields, is_dataclass
from types import ModuleType
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

SchemaType = Literal["object", "integer", "double", "string", "boolean", "array"]

TYPE_MAP: Dict[str, SchemaType] = {
    "int": "integer",
    "float": "double",
    "str": "string",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "List": "array",
    "Dict": "object",
}


def get_type_schema(type_hint: Any) -> Dict[str, Any]:
    """Convert a type hint to a JSON schema."""
    if type_hint is None or type_hint == inspect.Parameter.empty:
        return {"type": "object"}

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is Union:
        if type(None) in args:
            real_type = next(arg for arg in args if arg is not type(None))
            return get_type_schema(real_type)
        return {"type": "object"}

    if origin in (list, List):
        item_type = args[0] if args else Any
        return {"type": "array", "items": get_type_schema(item_type)}

    if origin in (dict, Dict):
        return {"type": "object"}

    if inspect.isclass(type_hint):
        if is_dataclass(type_hint):
            properties = {}
            required = []

            for field in fields(type_hint):
                field_schema = get_type_schema(field.type)
                properties[field.name] = field_schema
                if field.default == field.default_factory:
                    required.append(field.name)

            return {"type": "object", "properties": properties, "required": required}
        elif hasattr(type_hint, "__annotations__"):
            properties = {}
            required = []

            for name, field_type in type_hint.__annotations__.items():
                field_schema = get_type_schema(field_type)
                properties[name] = field_schema
                # For regular classes, we'll consider all annotated fields as required
                # unless they have a default value in __init__
                if hasattr(type_hint, "__init__"):
                    sig = inspect.signature(type_hint.__init__)
                    if (
                        name in sig.parameters
                        and sig.parameters[name].default == inspect.Parameter.empty
                    ):
                        required.append(name)
                else:
                    required.append(name)

            return {"type": "object", "properties": properties, "required": required}

    type_name = type_hint.__name__ if hasattr(type_hint, "__name__") else str(type_hint)
    schema_type = TYPE_MAP.get(type_name, "object")

    return {"type": schema_type}


def load_module(file_path: str) -> ModuleType:
    """Load a Python module from file path."""
    spec = importlib.util.spec_from_file_location("dynamic_module", file_path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["dynamic_module"] = module
    spec.loader.exec_module(module)
    return module


def generate_args(path: str) -> Dict[str, Dict[str, Any]]:
    """Generate input/output schema from main function type hints."""
    module = load_module(path)

    main_func = None
    for func_name in ["main", "run", "execute"]:
        if hasattr(module, func_name):
            main_func = getattr(module, func_name)
            break

    if not main_func:
        raise ValueError("No main function found in module")

    hints = get_type_hints(main_func)
    sig = inspect.signature(main_func)

    if not sig.parameters:
        return {"input": {}, "output": get_type_schema(hints.get("return", None))}

    input_param_name = next(iter(sig.parameters))
    input_schema = get_type_schema(hints.get(input_param_name))
    output_schema = get_type_schema(hints.get("return"))

    return {"input": input_schema, "output": output_schema}
