import importlib.util
import json
import logging
import os
import sys
import traceback
from os import environ as env
from pathlib import Path
from typing import Any, Dict, Optional, Union, Tuple
from dotenv import load_dotenv

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command, StateSnapshot, Interrupt

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

def load_langgraph_config(config_path: str = "langgraph.json") -> Dict[str, Any]:
    """Load the langgraph configuration file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        if 'graphs' not in config:
            raise ValueError("No 'graphs' field found in langgraph.json")
            
        return config
    except Exception as e:
        logger.error(f"[Executor] Failed to load langgraph.json: {str(e)}")
        raise

class GraphExecutor:
    def __init__(self, db_path: str = "uipath.db"):
        """Initialize the graph executor."""
        self.db_path = db_path
        self._graph: Optional[Union[StateGraph, CompiledStateGraph]] = None
        self._config: Optional[Dict[str, Any]] = None
        
        self.config = load_langgraph_config()
        self.graph_path = next(iter(self.config['graphs'].values()))

    def load_graph(self) -> Union[StateGraph, CompiledStateGraph]:
        """Load the graph from the specified script path."""
        try:
            file_path, graph_var = self.graph_path.split(":")
            
            if file_path.startswith("."):
                file_path = os.path.abspath(file_path)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Script not found: {file_path}")
            
            module_name = Path(file_path).stem
            
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module from: {file_path}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module 
            spec.loader.exec_module(module)
            
            graph = getattr(module, graph_var, None)
            if graph is None:
                raise AttributeError(f"Graph '{graph_var}' not found in {file_path}")
                
            if not isinstance(graph, (StateGraph, CompiledStateGraph)):
                raise TypeError(f"Expected StateGraph or CompiledStateGraph, got {type(graph)}")
                
            self._graph = graph
            return graph
            
        except Exception as e:
            logger.error(f"[Executor] Failed to load graph: {str(e)}")
            raise

    def get_interrupt_data(self, state: Optional[StateSnapshot]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if the graph execution was interrupted."""
        if not state:
            return False, None
            
        if not hasattr(state, "next") or not state.next:
            return False, None
            
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for interrupt in task.interrupts:
                    if isinstance(interrupt, Interrupt):
                        return True, interrupt.value
                
        return False, None

    async def execute(
        self,
        input_data: Any,
        config: Optional[Dict[str, Any]] = None,
        resume: bool = False
    ) -> Tuple[Any, bool, Optional[Dict[str, Any]]]:
        """Execute the loaded graph with the given input."""
        if not self._graph:
            self.load_graph()
            
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as memory:
            builder = self._graph.builder if isinstance(self._graph, CompiledStateGraph) else self._graph
            graph = builder.compile(checkpointer=memory)
            
            self._config = config or {}
            
            if resume:
                result = await graph.ainvoke(Command(resume=input_data), self._config)
            else:
                result = await graph.ainvoke(input_data, self._config)
            
            state = None
            try:
                state = await graph.aget_state(self._config)
            except Exception as e:
                logger.error(f"[Executor]: Failed to get state: {str(e)}")
            
            is_interrupted, interrupt_data = self.get_interrupt_data(state)
            
            if is_interrupted:
                logger.info(f"[Executor] Graph execution interrupted: {interrupt_data}")
            else:
                logger.info("[Executor] Graph execution completed successfully")
                
            return result, is_interrupted, interrupt_data

if __name__ == "__main__":
    import asyncio
    import json
    
    async def main():
        try:
            if len(sys.argv) < 2:
                logger.error(f"[Executor] Usage: executor.py [input_json]")
                sys.exit(1)
                
            input_data = json.loads(sys.argv[1])
            
            executor = GraphExecutor("uipath.db")
            config = {"configurable": {"thread_id": env.get("UIPATH_JOB_KEY", "default")}}
            
            result, is_interrupted, interrupt_data = await executor.execute(input_data, config)
            
            print(result)
            
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"[Executor] Error occurred: {str(e)}")
            logger.error(f"[Executor] Traceback: {traceback.format_exc()}")
            sys.exit(1)
            
    asyncio.run(main())