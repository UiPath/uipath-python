"""Whether the job's access token is being renewed in this process."""

# A count, so one renewal stopping does not switch off another.
_running = 0


def token_renewal_running() -> bool:
    """Whether a token renewal was started, and not yet stopped, in this process."""
    return _running > 0


def set_token_renewal_running(running: bool) -> None:
    """Count a token renewal as started (True) or stopped (False)."""
    global _running
    _running = _running + 1 if running else max(0, _running - 1)
