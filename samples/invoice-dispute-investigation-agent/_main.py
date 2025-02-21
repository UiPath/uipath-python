import dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from graph import builder

"""
This is the sample test application file for the LangGraph project.
It is used to run the graph and stream the results.
"""

dotenv.load_dotenv('.env')
graph = builder.compile(checkpointer= MemorySaver())

args = {
    "MismatchedItems": "Received Battery #bat14 (should be #bat17) Received Valve #val31 (should be #val15)",
    "Company": "Pacific Manufacturing",
    "Supplier": "Spectrum Parts",
    "SupplierWebsite": "https://acme-batteries.vercel.app/products/<SKU>"
}

config = { "configurable": {"thread_id": "4"} }

def stream_run(graph: CompiledStateGraph, args, config):
    for event in graph.stream(args, config, stream_mode="values"):
        if event.get('messages') is None or len(event["messages"]) == 0:
            print("===== event with no messages =====")
            print(event)
        else:
            event["messages"][-1].pretty_print()

stream_run(graph, args, config)
