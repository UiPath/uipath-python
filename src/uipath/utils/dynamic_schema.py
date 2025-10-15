"""Json schema to dynamic pydantic model."""

from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field, create_model


def jsonschema_to_pydantic(
    schema: dict[str, Any],
    definitions: Optional[dict[str, Any]] = None,
) -> Type[BaseModel]:
    """Convert a schema dict to a pydantic model.

    Modified version of https://github.com/kreneskyp/jsonschema-pydantic to account for two unresolved issues.

    Args:
        schema: JSON schema.
        definitions: Definitions dict. Defaults to `$def`.

    Returns: Pydantic model.
    """
    title = schema.get("title", "DynamicModel")
    assert isinstance(title, str), "Title of a model must be a string."

    description = schema.get("description", None)

    # top level schema provides definitions
    if definitions is None:
        if "$defs" in schema:
            definitions = schema["$defs"]
        elif "definitions" in schema:
            definitions = schema["definitions"]
        else:
            definitions = {}

    def convert_type(prop: dict[str, Any]) -> Any:
        if "$ref" in prop:
            ref_path = prop["$ref"].split("/")
            ref = definitions[ref_path[-1]]
            return jsonschema_to_pydantic(ref, definitions)

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

            if type_ == "array":
                item_type: Any = convert_type(prop.get("items", {}))
                assert isinstance(item_type, type)
                return List[item_type]  # noqa F821
            elif type_ == "object":
                if "properties" in prop:
                    return jsonschema_to_pydantic(prop, definitions)
                else:
                    return Dict[str, Any]
            else:
                return type_mapping.get(type_, Any)

        elif "allOf" in prop:
            combined_fields = {}
            for sub_schema in prop["allOf"]:
                model = jsonschema_to_pydantic(sub_schema, definitions)
                combined_fields.update(model.__annotations__)
            return create_model("CombinedModel", **combined_fields)

        elif "anyOf" in prop:
            unioned_types = tuple(
                convert_type(sub_schema) for sub_schema in prop["anyOf"]
            )
            return Union[unioned_types]
        elif prop == {} or "type" not in prop:
            return Any
        else:
            raise ValueError(f"Unsupported schema: {prop}")

    fields: dict[str, Any] = {}
    required_fields = schema.get("required", [])

    for name, prop in schema.get("properties", {}).items():
        pydantic_type = convert_type(prop)
        field_kwargs = {}
        if "default" in prop:
            field_kwargs["default"] = prop["default"]
        if name not in required_fields:
            # Note that we do not make this optional. This is due to a limitation in Pydantic/Python.
            # If we convert the Optional type back to json schema, it is represented as type | None.
            # pydantic_type = Optional[pydantic_type]

            if "default" not in field_kwargs:
                field_kwargs["default"] = None
        if "description" in prop:
            field_kwargs["description"] = prop["description"]
        if "title" in prop:
            field_kwargs["title"] = prop["title"]

        fields[name] = (pydantic_type, Field(**field_kwargs))

    convert_type(schema.get("properties", {}).get("choices", {}))

    model = create_model(title, **fields)
    if description:
        model.__doc__ = description
    return model
