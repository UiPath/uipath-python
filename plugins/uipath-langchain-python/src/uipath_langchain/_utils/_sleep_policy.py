import logging
from typing import Callable

from tenacity import (
    RetryCallState,
    _utils,
)


def before_sleep_log(
    logger: "logging.Logger",
    log_level: int,
    exc_info: bool = False,
) -> Callable[["RetryCallState"], None]:
    """Before call strategy that logs to some logger the attempt."""

    def log_it(retry_state: "RetryCallState") -> None:
        if retry_state.outcome is None:
            raise RuntimeError("log_it() called before outcome was set")

        if retry_state.next_action is None:
            raise RuntimeError("log_it() called before next_action was set")

        if retry_state.outcome.failed:
            ex = retry_state.outcome.exception()
            verb, value = "raised", f"{ex.__class__.__name__}: {ex}"
        else:
            verb, value = "returned", retry_state.outcome.result()

        if retry_state.fn is None:
            fn_name = "<unknown>"
        else:
            fn_name = _utils.get_callback_name(retry_state.fn)

        logger.log(
            log_level,
            f"Retrying #{retry_state.attempt_number} {fn_name} in {retry_state.next_action.sleep} seconds as it {verb} {value}.",
            {"retries": f"{retry_state.attempt_number}"},
        )

    return log_it
