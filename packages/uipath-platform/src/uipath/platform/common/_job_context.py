from ._config import UiPathConfig
from .constants import HEADER_JOB_KEY


def header_job_key() -> dict[str, str]:
    """Return the X-UiPath-JobKey header when the orchestrator job key is set.

    Returns an empty dict when ``UiPathConfig.job_key`` is unset or empty.
    """
    job_key = UiPathConfig.job_key
    if not job_key:
        return {}
    return {HEADER_JOB_KEY: job_key}
