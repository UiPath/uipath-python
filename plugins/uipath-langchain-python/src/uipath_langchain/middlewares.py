from uipath._cli.middlewares import Middlewares

from ._cli.cli_init import langgraph_init_middleware
from ._cli.cli_new import langgraph_new_middleware
from ._cli.cli_run import langgraph_run_middleware


def register_middleware():
    """This function will be called by the entry point system when uipath_langchain is installed"""
    Middlewares.register("init", langgraph_init_middleware)
    Middlewares.register("run", langgraph_run_middleware)
    Middlewares.register("new", langgraph_new_middleware)
