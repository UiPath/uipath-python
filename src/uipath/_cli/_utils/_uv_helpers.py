import os
import subprocess

from .._utils._console import ConsoleLogger

console = ConsoleLogger()


def handle_uv_operations(directory: str) -> None:
    """Handle UV package manager operations for the project.

    This function checks if UV is available and if the project uses UV,
    then ensures the lock file is up to date by running 'uv lock'.

    Args:
        directory: The project root directory where UV operations should be performed

    Note:
        This function will silently return if UV is not available or if the project
        doesn't use UV (no uv.lock file present).
    """
    if not is_uv_available():
        return
    if not is_uv_project(directory):
        return
    # Always run uv lock to ensure lock file is up to date
    run_uv_lock(directory)


def is_uv_available() -> bool:
    """Check if UV package manager is available in the system.

    Attempts to run 'uv --version' to verify UV is installed and accessible.

    Returns:
        bool: True if UV is available and working, False otherwise

    Note:
        This function will return False if:
        - UV is not installed
        - UV command fails to execute
        - Any unexpected error occurs during version check
    """
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True, timeout=20)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    except Exception as e:
        console.warning(
            f"An unexpected error occurred while checking uv availability: {str(e)}"
        )
        return False


def is_uv_project(directory: str) -> bool:
    """Check if the project uses UV package manager.

    Determines if this is a UV project by checking for the presence
    of a uv.lock file in the project directory.

    Args:
        directory: The project root directory to check

    Returns:
        bool: True if uv.lock exists, indicating a UV project, False otherwise
    """
    uv_lock_path = os.path.join(directory, "uv.lock")

    # If uv.lock exists, it's definitely a uv project
    if os.path.exists(uv_lock_path):
        return True

    return False


def run_uv_lock(directory: str) -> bool:
    """Run 'uv lock' command to update the project's lock file.

    Executes UV lock command to ensure dependencies are properly locked
    and the lock file is up to date.

    Args:
        directory: The project root directory where the lock command should be run

    Returns:
        bool: True if the lock command succeeds, False if it fails for any reason

    Note:
        This function will log warnings and return False if:
        - The UV command fails to execute
        - UV is not found in the system
        - The lock command times out (60 seconds)
        - Any unexpected error occurs during execution
    """
    try:
        subprocess.run(
            ["uv", "lock"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return True
    except subprocess.CalledProcessError as e:
        console.warning(f"uv lock failed: {e.stderr}")
        return False
    except FileNotFoundError:
        console.warning("uv command not found. Skipping lock file update.")
        return False
    except Exception as e:
        console.warning(f"An unexpected error occurred while running uv lock: {str(e)}")
        return False
