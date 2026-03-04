from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from uipath.tracing import traced
from llama_index.llms.openai import OpenAI
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@traced()
def my_custom_nested_traced_function(input: str) -> str:
    logger.warning(f"Testing nested traced from uipath: {input}")
    # Custom function to process the input
    return { "a-nested": "HARD-CODED-OUTPUT-2" }


@traced()
def my_custom_traced_function(input: str) -> str:
    logger.warning(f"Testing traced from uipath: {input}")

    my_custom_nested_traced_function(input)
    # Custom function to process the input
    return { "a": "HARD-CODED-OUTPUT-2" }

@traced(name="factorial")
async def factorial(i: int=0) -> int:
    logger.info(f"Calculating factorial of {i}")
    if i <= 1:
        return 1
    return i * await factorial(i=i - 1)


class TopicEvent(StartEvent):
    topic: str


class JokeEvent(Event):
    joke: str


class CritiqueEvent(StopEvent):
    joke: str
    critique: str


class JokeFlow(Workflow):
    llm = OpenAI()

    @step
    async def generate_joke(self, ev: TopicEvent) -> JokeEvent:

        my_custom_traced_function("test-1")
        my_custom_traced_function("test-2")
        await factorial(5)

        response = "Random joke"
        return JokeEvent(joke=str(response))

    @step
    async def critique_joke(self, ev: JokeEvent) -> CritiqueEvent:
        joke = ev.joke
        return CritiqueEvent(joke=joke, critique="Just a critique")


workflow = JokeFlow(timeout=60, verbose=False)
