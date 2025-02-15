from typing import Optional

import click
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ._utils._graph import LangGraphConfig


async def handle_run(graph_name: Optional[str] = None, db_path: str = "uipath.db"):
    """Enhanced run command with LangGraph support"""
    try:
        config = LangGraphConfig()
        if not config.exists:
            raise click.UsageError("No langgraph.json found. Please initialize first.")

        # If no specific graph is specified and there's only one, use that
        if not graph_name and len(config.graphs) == 1:
            graph_config = config.graphs[0]
        elif not graph_name:
            raise click.UsageError(
                f"Multiple graphs available. Please specify one of: {', '.join(g.name for g in config.graphs)}"
            )
        else:
            graph_config = config.get_graph(graph_name)
            if not graph_config:
                raise click.UsageError(f"Graph '{graph_name}' not found")

        graph = graph_config.load_graph()

        async with AsyncSqliteSaver.from_conn_string(db_path) as memory:
            builder = graph.builder if hasattr(graph, "builder") else graph
            compiled_graph = builder.compile(checkpointer=memory)

            # TODO: Add your execution logic here

    except Exception as e:
        click.echo(f"Error during execution: {str(e)}")
        raise
