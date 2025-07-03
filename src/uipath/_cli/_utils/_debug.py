"""Debug utilities for UiPath CLI."""

import os

from ._console import ConsoleLogger

console = ConsoleLogger()


def setup_debugging(debug: bool, debug_port: int = 5678) -> bool:
    """Setup debugging with debugpy if requested.

    Args:
        debug: Whether to enable debugging
        debug_port: Port for the debug server (default: 5678)

    Returns:
        bool: True if debugging was setup successfully or not requested, False on error
    """
    if not debug:
        return True

    # Set environment variables to improve debugging
    os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
    os.environ["PYDEVD_USE_FRAME_EVAL"] = "NO"

    # Try to import debugpy, log warning if not available
    try:
        import debugpy  # type: ignore[import-not-found]
    except ImportError:
        console.warning(
            "debugpy not found, please install it and retry: '[uv] pip install debugpy'"
        )
        return False

    # Configure debugpy for better breakpoint handling
    try:
        # Clear any existing listeners
        debugpy.configure(subProcess=False)

        debugpy.listen(debug_port)
        console.info(f"🐛 Debug server started on port {debug_port}")
        console.info("📌 Waiting for debugger to attach...")
        console.info("  - VS Code: Run -> Start Debugging -> Python: Remote Attach")
        console.link(
            " CLI Documentation reference: ",
            "https://uipath.github.io/uipath-python/cli/#run",
        )

        debugpy.wait_for_client()
        console.success("Debugger attached successfully!")

        return True
    except Exception as e:
        console.error(f"Failed to start debug server on port {debug_port}: {str(e)}")
        return False
