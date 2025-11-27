"""Tests for the _cleanup_schema function in LLM Gateway Service."""

from typing import List, Optional

from pydantic import BaseModel

from uipath._services.llm_gateway_service import _cleanup_schema


# Simple test models
class SimpleModel(BaseModel):
    name: str
    age: int
    active: bool


class ModelWithList(BaseModel):
    names: List[str]
    numbers: List[int]


class ModelWithOptional(BaseModel):
    required_field: str
    optional_field: Optional[str] = None


# Complex nested models for comprehensive testing
class Task(BaseModel):
    task_id: int
    description: str
    completed: bool


class Project(BaseModel):
    project_id: int
    name: str
    tasks: List[Task]


class Team(BaseModel):
    team_id: int
    team_name: str
    members: List[str]
    projects: List[Project]


class Department(BaseModel):
    department_id: int
    department_name: str
    teams: List[Team]


class Company(BaseModel):
    company_id: int
    company_name: str
    departments: List[Department]


class TestCleanupSchema:
    """Test cases for the _cleanup_schema function."""

    def test_simple_model_cleanup(self):
        """Test cleanup of a simple model without nested structures."""
        schema = _cleanup_schema(SimpleModel)

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "required" in schema
        assert set(schema["required"]) == {"name", "age", "active"}

        # Check properties are cleaned (no titles)
        properties = schema["properties"]
        assert "name" in properties
        assert "age" in properties
        assert "active" in properties

        # Ensure no 'title' fields are present
        for _prop_name, prop_def in properties.items():
            assert "title" not in prop_def

    def test_model_with_list_cleanup(self):
        """Test cleanup of a model with list fields."""
        schema = _cleanup_schema(ModelWithList)

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False

        # Check list properties
        names_prop = schema["properties"]["names"]
        assert names_prop["type"] == "array"
        assert "items" in names_prop
        assert names_prop["items"]["type"] == "string"
        # Ensure no 'title' in items
        assert "title" not in names_prop["items"]

        numbers_prop = schema["properties"]["numbers"]
        assert numbers_prop["type"] == "array"
        assert "items" in numbers_prop
        assert numbers_prop["items"]["type"] == "integer"
        assert "title" not in numbers_prop["items"]

    def test_model_with_optional_cleanup(self):
        """Test cleanup of a model with optional fields."""
        schema = _cleanup_schema(ModelWithOptional)

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False

        # Only required_field should be in required array
        assert schema["required"] == ["required_field", "optional_field"]

        # Both fields should be in properties
        assert "required_field" in schema["properties"]
        assert "optional_field" in schema["properties"]

    def test_complex_nested_model_cleanup(self):
        """Test cleanup of the complex nested Company model."""
        schema = _cleanup_schema(Company)

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"company_id", "company_name", "departments"}

        # Check top-level properties
        properties = schema["properties"]
        assert "company_id" in properties
        assert "company_name" in properties
        assert "departments" in properties

        # Check departments is array of objects
        departments_prop = properties["departments"]
        assert departments_prop["type"] == "array"
        assert "items" in departments_prop
        assert "title" not in departments_prop["items"]

        # Verify no 'title' fields exist anywhere in the schema
        self._assert_no_titles_recursive(schema)

    def test_schema_structure_integrity(self):
        """Test that the cleaned schema maintains proper JSON Schema structure."""
        schema = _cleanup_schema(Company)

        # Must have these top-level keys
        required_keys = {"type", "properties", "required", "additionalProperties"}
        assert all(key in schema for key in required_keys)

        # Type must be object
        assert schema["type"] == "object"

        # additionalProperties must be False
        assert schema["additionalProperties"] is False

        # Properties must be a dict
        assert isinstance(schema["properties"], dict)

        # Required must be a list
        assert isinstance(schema["required"], list)

    def test_email_field_handling(self):
        """Test that EmailStr fields are properly handled."""
        schema = _cleanup_schema(Team)

        members_prop = schema["properties"]["members"]
        assert members_prop["type"] == "array"

        # EmailStr should be treated as string with format
        items = members_prop["items"]
        assert items["type"] == "string"
        # Email format might be present
        if "format" in items:
            assert items["format"] == "email"

    def test_nested_objects_cleanup(self):
        """Test that nested objects are properly cleaned."""
        schema = _cleanup_schema(Department)

        # Check teams property (array of Team objects)
        teams_prop = schema["properties"]["teams"]
        assert teams_prop["type"] == "array"
        assert "items" in teams_prop

        # The items should not have title
        team_items = teams_prop["items"]
        assert "title" not in team_items

        # If it's a nested object, check its properties
        if "properties" in team_items:
            for _prop_name, prop_def in team_items["properties"].items():
                assert "title" not in prop_def

    def _assert_no_titles_recursive(self, obj):
        """Recursively assert that no 'title' fields exist in the schema."""
        if isinstance(obj, dict):
            assert "title" not in obj, f"Found 'title' field in: {obj}"
            for value in obj.values():
                self._assert_no_titles_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                self._assert_no_titles_recursive(item)

    def test_function_returns_dict(self):
        """Test that the function returns a dictionary."""
        result = _cleanup_schema(SimpleModel)
        assert isinstance(result, dict)

    def test_function_with_inheritance(self):
        """Test cleanup with model inheritance."""

        class BaseEntity(BaseModel):
            id: int
            created_at: str

        class ExtendedEntity(BaseEntity):
            name: str
            description: Optional[str] = None

        schema = _cleanup_schema(ExtendedEntity)

        # Should include fields from both base and derived class
        properties = schema["properties"]
        assert "id" in properties
        assert "created_at" in properties
        assert "name" in properties
        assert "description" in properties

        # Required fields from both classes
        required_fields = set(schema["required"])
        assert "id" in required_fields
        assert "created_at" in required_fields
        assert "name" in required_fields
        assert "description" in required_fields
