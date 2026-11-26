"""Whether the job's access token is being renewed in this process."""

_running = False


def token_renewal_running() -> bool:
    """Whether the job's token renewal was started, and not yet stopped, in this process."""
    return _running


def set_token_renewal_running(running: bool) -> None:
    """Mark the renewal of the job's token as running or stopped."""
    global _running
    _running = running
