from importlib.metadata import entry_points


def load_runtime_factories():
    """Auto-discover and register all factory plugins."""
    for ep in entry_points(group="uipath.runtime.factories"):
        try:
            register_func = ep.load()
            register_func()
        except Exception as e:
            print(f"Failed to load factory {ep.name}: {e}")
