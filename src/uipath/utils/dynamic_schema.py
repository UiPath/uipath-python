"""Json schema to dynamic pydantic model."""

from enum import Enum
from typing import Any, Dict, List, Type, Union

from pydantic import BaseModel, Field, create_model


def jsonschema_to_pydantic(
    schema: dict[str, Any],
) -> Type[BaseModel]:
    """Convert a schema dict to a pydantic model.

    Modified version of https://github.com/kreneskyp/jsonschema-pydantic to account for three unresolved issues.
      1. Support for title
      2. Better representation of optionals.
      3. Support for optional

    Args:
        schema: JSON schema.
        definitions: Definitions dict. Defaults to `$def`.

    Returns: Pydantic model.
    """
    dynamic_type_counter = 0
    combined_model_counter = 0

    def convert_type(prop: dict[str, Any]) -> Any:
        nonlocal dynamic_type_counter, combined_model_counter
        if "$ref" in prop:
            # This is the full path. It will be updated in update_forward_refs.
            return prop["$ref"].split("/")[-1].capitalize()

        if "type" in prop:
            type_mapping = {
                "string": str,
                "number": float,
                "integer": int,
                "boolean": bool,
                "array": List,
                "object": Dict[str, Any],
                "null": None,
            }

            type_ = prop["type"]

            if "enum" in prop:
                dynamic_members = {
                    f"KEY_{i}": value for i, value in enumerate(prop["enum"])
                }

                base_type: Any = type_mapping.get(type_, Any)

                class DynamicEnum(base_type, Enum):
                    pass

                type_ = DynamicEnum(prop.get("title", "DynamicEnum"), dynamic_members)  # type: ignore[call-arg]
                return type_
            elif type_ == "array":
                item_type: Any = convert_type(prop.get("items", {}))
                return List[item_type]  # noqa F821
            elif type_ == "object":
                if "properties" in prop:
                    if "title" in prop and prop["title"]:
                        title = prop["title"]
                    else:
                        title = f"DynamicType_{dynamic_type_counter}"
                        dynamic_type_counter += 1

                    fields: dict[str, Any] = {}
                    required_fields = prop.get("required", [])

                    for name, property in prop.get("properties", {}).items():
                        pydantic_type = convert_type(property)
                        field_kwargs = {}
                        if "default" in property:
                            field_kwargs["default"] = property["default"]
                        if name not in required_fields:
                            # Note that we do not make this optional. This is due to a limitation in Pydantic/Python.
                            # If we convert the Optional type back to json schema, it is represented as type | None.
                            # pydantic_type = Optional[pydantic_type]

                            if "default" not in field_kwargs:
                                field_kwargs["default"] = None
                        if "description" in property:
                            field_kwargs["description"] = property["description"]
                        if "title" in property:
                            field_kwargs["title"] = property["title"]

                        fields[name] = (pydantic_type, Field(**field_kwargs))

                    object_model = create_model(title, **fields)
                    if "description" in prop:
                        object_model.__doc__ = prop["description"]
                    return object_model
                else:
                    return Dict[str, Any]
            else:
                return type_mapping.get(type_, Any)

        elif "allOf" in prop:
            combined_fields = {}
            for sub_schema in prop["allOf"]:
                model = convert_type(sub_schema)
                combined_fields.update(model.__annotations__)
            combined_model = create_model(
                f"CombinedModel_{combined_model_counter}", **combined_fields
            )
            combined_model_counter += 1
            return combined_model

        elif "anyOf" in prop:
            unioned_types = tuple(
                convert_type(sub_schema) for sub_schema in prop["anyOf"]
            )
            return Union[unioned_types]
        elif prop == {} or "type" not in prop:
            return Any
        else:
            raise ValueError(f"Unsupported schema: {prop}")

    namespace: dict[str, Any] = {}
    for name, definition in schema.get("$defs", schema.get("definitions", {})).items():
        model = convert_type(definition)
        namespace[name.capitalize()] = model
    model = convert_type(schema)
    model.model_rebuild(force=True, _types_namespace=namespace)
    return model
