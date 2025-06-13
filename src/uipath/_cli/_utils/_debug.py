"""Debug utilities for UiPath CLI."""

import os
import subprocess
import sys

from ._console import ConsoleLogger

console = ConsoleLogger()


def _install_debugpy() -> bool:
    """Install debugpy using various methods.

    Returns:
        bool: True if installation was successful, False otherwise
    """
    console.info("📦 Installing debugpy for debugging functionality...")

    try:
        subprocess.run(
            ["uv", "add", "debugpy>=1.8.0"], capture_output=True, text=True, check=True
        )
        console.success("✅ debugpy installed successfully using uv add!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.info("uv add failed, trying uv pip install...")

    try:
        subprocess.run(
            ["uv", "pip", "install", "debugpy>=1.8.0"],
            capture_output=True,
            text=True,
            check=True,
        )
        console.success("✅ debugpy installed successfully using uv pip!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.info("uv pip install failed, trying pip install...")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "debugpy>=1.8.0"],
            capture_output=True,
            text=True,
            check=True,
        )
        console.success("✅ debugpy installed successfully using pip!")
        return True
    except subprocess.CalledProcessError as e:
        console.info(f"pip install failed: {e.stderr}")
    except FileNotFoundError:
        console.info("pip not found, trying to install pip...")

    try:
        # Try to install pip using ensurepip
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            capture_output=True,
            text=True,
            check=True,
        )
        console.info("pip installed successfully, now installing debugpy...")

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "debugpy>=1.8.0"],
            capture_output=True,
            text=True,
            check=True,
        )
        console.success("✅ debugpy installed successfully after installing pip!")
        return True
    except subprocess.CalledProcessError as e:
        console.error(f"Failed to install pip or debugpy: {e.stderr}")

    console.error("❌ Failed to install debugpy automatically.")
    console.info("Please install debugpy manually using one of these methods:")
    console.info("  1. uv add debugpy>=1.8.0")
    console.info("  2. pip install debugpy>=1.8.0")
    console.info("  3. python -m pip install debugpy>=1.8.0")
    return False


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

    # Try to import debugpy, install if not available
    try:
        import debugpy
    except ImportError:
        console.info("🔍 debugpy not found, installing it...")
        if not _install_debugpy():
            return False
        try:
            import debugpy
        except ImportError:
            console.error("Failed to import debugpy even after installation")
            console.info("Try restarting your terminal or virtual environment")
            return False

    # Configure debugpy for better breakpoint handling
    try:
        # Clear any existing listeners
        debugpy.configure(subProcess=False)

        debugpy.listen(debug_port)
        console.info(f"🐛 Debug server started on port {debug_port}")
        console.info("📌 Waiting for debugger to attach...")
        console.info(
            f"   - In PyCharm: Run -> Attach to Process -> localhost:{debug_port}"
        )
        console.info(
            "   - In VS Code/Cursor: Run -> Start Debugging -> Python: Remote Attach"
        )
        console.info(
            "💡 TIP: Make sure to set breakpoints BEFORE attaching the debugger!"
        )

        debugpy.wait_for_client()
        console.success("✅ Debugger attached successfully!")

        # Enable breakpoint debugging
        debugpy.breakpoint()
        console.info(
            "🎯 Breakpoint debugging enabled - your breakpoints should work now!"
        )

        return True
    except Exception as e:
        console.error(f"Failed to start debug server on port {debug_port}: {str(e)}")
        return False


def add_debug_options(command_func):
    """Decorator to add debug options to a click command.

    Args:
        command_func: The click command function to decorate

    Returns:
        The decorated function with debug options added
    """
    import click

    command_func = click.option(
        "--debug-port",
        type=int,
        default=5678,
        help="Port for the debug server (default: 5678)",
    )(command_func)

    command_func = click.option(
        "--debug",
        is_flag=True,
        help="Enable debugging with debugpy. The process will wait for a debugger to attach.",
    )(command_func)

    return command_func
