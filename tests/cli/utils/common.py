import os


def configure_env_vars(env_vars: dict[str, str]):
    os.environ.clear()
    os.environ.update(env_vars)
