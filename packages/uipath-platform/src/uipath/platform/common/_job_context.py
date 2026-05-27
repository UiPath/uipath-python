from os import environ as env

from .constants import ENV_JOB_KEY, HEADER_JOB_KEY


def header_job_key() -> dict[str, str]:
    """Return the X-UiPath-JobKey header when the orchestrator job key is set.

    Reads ``UIPATH_JOB_KEY`` from the process environment at call time so that
    services can associate outbound requests with the originating orchestrator
    job. Returns an empty dict when the env var is unset or empty.
    """
    job_key = env.get(ENV_JOB_KEY)
    if not job_key:
        return {}
    return {HEADER_JOB_KEY: job_key}
