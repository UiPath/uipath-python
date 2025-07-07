import os
from typing import Dict


def configure_env_vars(env_vars: Dict[str, str]):
    os.environ.clear()
    os.environ.update(env_vars)
