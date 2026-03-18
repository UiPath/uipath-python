from importlib.metadata import entry_points
from pathlib import Path


def load_runtime_factories():
    """Auto-discover and register all factory plugins."""
    for ep in entry_points(group="uipath.runtime.factories"):
        try:
            register_func = ep.load()
            register_func()
        except Exception as e:
            print(f"Failed to load factory {ep.name}: {e}")


def get_factory_search_path(entrypoint: str | None) -> str:
    """Derive the config file search path from an entrypoint path.

    When an entrypoint lives in a subdirectory (e.g. agents/agent1/agent.json),
    the factory registry needs to search that directory for config files like
    agent.json or langgraph.json.

    Args:
        entrypoint: Optional entrypoint path, possibly with :function notation.

    Returns:
        Directory to search for factory config files, defaults to ".".
    """
    if not entrypoint:
        return "."
    # Strip function notation (e.g., "src/main.py:main" -> "src/main.py")
    file_path = entrypoint.split(":")[0]
    parent = str(Path(file_path).parent)
    return parent if parent != "." else "."
