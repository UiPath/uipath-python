from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.openai import OpenAI


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
        response = "Random joke"
        return JokeEvent(joke=str(response))

    @step
    async def critique_joke(self, ev: JokeEvent) -> CritiqueEvent:
        joke = ev.joke
        return CritiqueEvent(joke=joke, critique="Just a critique")


workflow = JokeFlow(timeout=60, verbose=False)
