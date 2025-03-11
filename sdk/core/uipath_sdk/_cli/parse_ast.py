# type: ignore

import ast
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .._services import AssetsService, BucketsService, ProcessesService
from .._utils import get_inferred_bindings_names


@dataclass
class ServiceMethodCall:
    """Represents a call to a service method with its parameters."""

    method_name: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0

    def extract_string_arg(self, index: int = 0) -> Optional[str]:
        """Extract a string argument at the given position if it exists."""
        if index < len(self.args):
            if isinstance(self.args[index], str):
                return self.args[index]
            elif isinstance(self.args[index], (int, float, bool)):
                return str(self.args[index])
        return None


service_name_resource_mapping = {
    "assets": "asset",
    "processes": "process",
    "buckets": "bucket",
}


@dataclass
class ServiceUsage:
    """Collects all method calls for a specific service type."""

    service_name: str
    method_calls: List[ServiceMethodCall] = field(default_factory=list)

    def get_component_info(self) -> List[Dict[str, str]]:
        """Extract component names and folders based on the service type."""
        result = []

        if self.service_name == "assets":
            for call in self.method_calls:
                inferred_bindings = get_inferred_bindings_names(AssetsService)
                if call.method_name in inferred_bindings:
                    name = extract_parameter(
                        call, inferred_bindings[call.method_name]["name"], 0
                    )
                    folder_path = extract_parameter(
                        call, inferred_bindings[call.method_name]["folder_path"]
                    )
                    if name:
                        result.append(
                            {
                                "name": name,
                                "folder": folder_path or "",
                                "method": call.method_name,
                            }
                        )

        elif self.service_name == "processes":
            for call in self.method_calls:
                inferred_bindings = get_inferred_bindings_names(ProcessesService)
                if call.method_name in inferred_bindings:
                    name = extract_parameter(
                        call, inferred_bindings[call.method_name]["name"], 0
                    )
                    folder_path = extract_parameter(
                        call, inferred_bindings[call.method_name]["folder_path"]
                    )
                    if name:
                        result.append(
                            {
                                "name": name,
                                "folder": folder_path or "",
                                "method": call.method_name,
                            }
                        )

        elif self.service_name == "buckets":
            for call in self.method_calls:
                inferred_bindings = get_inferred_bindings_names(BucketsService)
                if call.method_name in inferred_bindings:
                    name = extract_parameter(
                        call, inferred_bindings[call.method_name]["name"], 0
                    )
                    folder_path = extract_parameter(
                        call, inferred_bindings[call.method_name]["folder_path"]
                    )
                    if name:
                        result.append(
                            {
                                "name": name,
                                "folder": folder_path or "",
                                "method": call.method_name,
                            }
                        )

        return result


def extract_parameter(
    method_call: ServiceMethodCall,
    param_name: str,
    position_index: Optional[int] = None,
) -> Optional[Any]:
    """
    Extract a parameter from a method call, checking both keyword and positional arguments.

    Args:
        method_call: The ServiceMethodCall object
        param_name: The name of the parameter to extract
        position_index: Optional position of the parameter if passed as a positional argument

    Returns:
        The parameter value if found, None otherwise
    """
    if param_name in method_call.kwargs:
        return method_call.kwargs[param_name]

    if position_index is not None and position_index < len(method_call.args):
        return method_call.args[position_index]

    return None


def parse_local_module(
    module_path: str, base_dir: str
) -> Dict[str, List[Dict[str, str]]]:
    """
    Parse a local module and extract SDK usage.

    Args:
        module_path: Import path of the module (e.g., 'myapp.utils')
        base_dir: Base directory to resolve relative imports

    Returns:
        Dictionary of SDK usage from the module
    """
    # Convert module path to file path
    file_path = os.path.join(base_dir, *module_path.split(".")) + ".py"

    # Check if the file exists
    if not os.path.exists(file_path):
        # Try as a package with __init__.py
        file_path = os.path.join(base_dir, *module_path.split("."), "__init__.py")
        if not os.path.exists(file_path):
            return {}

    # Parse the module
    try:
        with open(file_path, "r") as f:
            source_code = f.read()
        return parse_sdk_usage(source_code, base_dir)
    except Exception:
        return {}


class UiPathSDKTracker:
    """Tracks UiPathSDK usage throughout the code."""

    def __init__(self, source_code: str, base_dir: str = ""):
        self.source_code = source_code
        self.base_dir = base_dir
        self.tree = ast.parse(source_code)
        self.sdk_imports: Dict[str, str] = {}  # Import alias -> original module
        self.sdk_instances: Dict[str, str] = {}  # Instance name -> class
        self.local_imports: List[str] = []  # List of local module imports
        self.service_usage: Dict[str, ServiceUsage] = {
            "assets": ServiceUsage("assets"),
            "processes": ServiceUsage("processes"),
            "buckets": ServiceUsage("buckets"),
            "actions": ServiceUsage("actions"),
            "context_grounding": ServiceUsage("context_grounding"),
            "api_client": ServiceUsage("api_client"),
        }

    def analyze(self) -> None:
        """Run all analysis steps."""
        self._find_imports()
        self._find_instances()
        self._find_method_calls()

    def _find_imports(self) -> None:
        """Find all imports of UiPathSDK and local modules."""

        class ImportVisitor(ast.NodeVisitor):
            def __init__(self):
                self.imports = {}
                self.local_imports = []

            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name == "uipath_sdk":
                        self.imports[alias.asname or alias.name] = alias.name
                    elif (
                        not alias.name.startswith(("__", "builtins", "typing"))
                        and "." not in alias.name
                    ):
                        # Potential local import
                        self.local_imports.append(alias.name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                if node.module == "uipath_sdk":
                    for alias in node.names:
                        if alias.name == "UiPathSDK":
                            self.imports[alias.asname or alias.name] = (
                                "uipath_sdk.UiPathSDK"
                            )
                elif node.module and not node.module.startswith(
                    ("__", "builtins", "typing")
                ):
                    # Potential local import
                    self.local_imports.append(node.module)
                self.generic_visit(node)

        visitor = ImportVisitor()
        visitor.visit(self.tree)
        self.sdk_imports = visitor.imports
        self.local_imports = visitor.local_imports

    def _find_instances(self) -> None:
        """Find all instances created from UiPathSDK."""

        class InstanceVisitor(ast.NodeVisitor):
            def __init__(self, sdk_imports):
                self.sdk_imports = sdk_imports
                self.instances = {}

            def visit_Assign(self, node):
                if isinstance(node.value, ast.Call):
                    call = node.value
                    if (
                        isinstance(call.func, ast.Name)
                        and call.func.id in self.sdk_imports
                    ):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.instances[target.id] = "UiPathSDK"
                self.generic_visit(node)

        visitor = InstanceVisitor(self.sdk_imports)
        visitor.visit(self.tree)
        self.sdk_instances = visitor.instances

    def _find_method_calls(self) -> None:
        """Find all method calls on UiPathSDK instances."""

        class MethodCallVisitor(ast.NodeVisitor):
            def __init__(self, source_code, sdk_instances, service_usage):
                self.source_code = source_code
                self.sdk_instances = sdk_instances
                self.service_usage = service_usage

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute) and isinstance(
                    node.func.value, ast.Attribute
                ):
                    if (
                        isinstance(node.func.value.value, ast.Name)
                        and node.func.value.value.id in self.sdk_instances
                    ):
                        service_name = node.func.value.attr
                        method_name = node.func.attr

                        if service_name in self.service_usage:
                            # Extract arguments
                            args = []
                            for arg in node.args:
                                if isinstance(arg, ast.Constant) and isinstance(
                                    arg.value, str
                                ):
                                    args.append(arg.value)
                                elif isinstance(arg, ast.Constant):
                                    # Handle non-string constants normally
                                    args.append(arg.value)
                                else:
                                    # For expressions and variables, prefix with EXPR$
                                    args.append(
                                        f"{ast.get_source_segment(self.source_code, arg)}"
                                    )

                            kwargs = {}
                            for keyword in node.keywords:
                                if isinstance(keyword.value, ast.Constant):
                                    kwargs[keyword.arg] = keyword.value.value
                                else:
                                    kwargs[keyword.arg] = (
                                        f"{ast.get_source_segment(self.source_code, keyword.value)}"
                                    )

                            method_call = ServiceMethodCall(
                                method_name=method_name,
                                args=args,
                                kwargs=kwargs,
                                line_number=node.lineno,
                            )
                            self.service_usage[service_name].method_calls.append(
                                method_call
                            )

                self.generic_visit(node)

        visitor = MethodCallVisitor(
            self.source_code, self.sdk_instances, self.service_usage
        )
        visitor.visit(self.tree)

    def get_results(self) -> Dict[str, List[Dict[str, str]]]:
        """Get the analysis results organized by service type."""
        results = {}
        for service_name, usage in self.service_usage.items():
            components = usage.get_component_info()
            if components:
                results[service_name] = components
        return results


def parse_sdk_usage(
    source_code: str, base_dir: str = ""
) -> Dict[str, List[Dict[str, str]]]:
    """
    Parse the source code and return UiPathSDK usage information.

    Args:
        source_code: The Python source code to analyze
        base_dir: Base directory to resolve relative imports

    Returns:
        Dictionary of SDK usage information
    """
    tracker = UiPathSDKTracker(source_code, base_dir)
    tracker.analyze()
    results = tracker.get_results()

    # Parse local imports recursively
    if base_dir:
        for module_path in tracker.local_imports:
            module_results = parse_local_module(module_path, base_dir)

            # Merge results
            for service_name, components in module_results.items():
                if service_name in results:
                    results[service_name].extend(components)
                else:
                    results[service_name] = components

    return results


def convert_to_bindings_format(sdk_usage_data):
    """
    Convert the output of parse_sdk_usage to a structure similar to bindings_v2.json

    Args:
        sdk_usage_data: Dictionary output from parse_sdk_usage

    Returns:
        Dictionary in bindings_v2.json format
    """
    bindings = {"version": "2.0", "resources": []}

    for resource_type, components in sdk_usage_data.items():
        for component in components:
            resource_name = component.get("name", "")
            folder_path = component.get("folder", None)
            method_name = component.get("method", "Unknown")

            name = resource_name
            if "/" in resource_name:
                parts = resource_name.split(".")
                if len(parts) > 1:
                    name = parts[-1]
            elif "." in resource_name:
                parts = resource_name.split(".")
                if len(parts) > 1:
                    name = parts[-1]

            key = resource_name
            if folder_path and "." not in resource_name and "/" not in resource_name:
                if "/" in folder_path:
                    key = f"{folder_path}.{name}"
                else:
                    key = f"{folder_path}.{name}"

            resource_entry = {
                "resource": service_name_resource_mapping[resource_type],
                "key": key,
                "value": {
                    "name": {
                        "defaultValue": name,
                        "isExpression": not isinstance(name, str) or "{" in name,
                        "displayName": "Name",
                    }
                },
                "metadata": {
                    "ActivityName": method_name,
                    "BindingsVersion": "2.1",
                    "DisplayLabel": "FullName",
                },
            }

            if folder_path:
                resource_entry["value"]["folderPath"] = {
                    "defaultValue": folder_path,
                    "isExpression": not isinstance(folder_path, str)
                    or "{" in folder_path,
                    "displayName": "Folder Path",
                }

            bindings["resources"].append(resource_entry)

    return bindings


def generate_bindings_json(file_path: str) -> str:
    """
    Generate bindings JSON from a Python file.

    Args:
        file_path: Path to the Python file to analyze

    Returns:
        JSON string representation of the bindings
    """
    try:
        with open(file_path, "r") as f:
            source_code = f.read()

        # Get the base directory for resolving imports
        base_dir = os.path.dirname(os.path.abspath(file_path))

        sdk_usage = parse_sdk_usage(source_code, base_dir)
        bindings = convert_to_bindings_format(sdk_usage)

        return bindings

    except Exception as e:
        raise Exception(f"Error generating bindings JSON: {e}") from e
