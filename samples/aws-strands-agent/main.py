import os

from strands import Agent, tool
from strands_tools import calculator, current_time
from strands.models.openai import OpenAIModel

model = OpenAIModel(
    client_args={
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    model_id="gpt-4o",
    params={
        "max_tokens": 1000,
        "temperature": 0.7,
    }
)
from pydantic import BaseModel

class InputModel(BaseModel):
    custom_query: str | None = None

class OutputModel(BaseModel):
    output: str

@tool
def letter_counter(word: str, letter: str) -> int:
    """
    Count occurrences of a specific letter in a word.

    Args:
        word (str): The input word to search in
        letter (str): The specific letter to count

    Returns:
        int: The number of occurrences of the letter in the word
    """
    if not isinstance(word, str) or not isinstance(letter, str):
        return 0

    if len(letter) != 1:
        raise ValueError("The 'letter' parameter must be a single character")

    return word.lower().count(letter.lower())

def main(input_model: InputModel) -> OutputModel:
    query = """
    I have 4 requests:

    1. What is the time right now?
    2. Calculate 3111696 / 74088
    3. Tell me how many letter R's are in the word "strawberry" 🍓
    """
    if custom_query := input_model.custom_query:
        query = custom_query

    agent = Agent(tools=[calculator, current_time, letter_counter], model=model)
    return OutputModel(output=str(agent(query).message["content"][0]["text"]))
