import os
from typing import Literal

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

MODEL = "gpt-5.4-nano"

INSTRUCTIONS = """You classify restaurant reviews by their main complaint or praise.
Labels:
- food: taste, quality, or temperature of the food
- service: staff, waiting time, or friendliness
- price: cost or value for money
- unclear: too vague to classify"""

REVIEWS = [
    "The pasta was cold and bland.",
    "Our waiter ignored us for 20 minutes.",
    "Way too expensive for such small portions.",
    "It was fine I guess.",
    "Lovely staff, but the steak was overcooked.",
]


class ReviewLabel(BaseModel):
    # reason comes first so the model explains before it picks a label
    reason: str = Field(description="One short sentence explaining the choice")
    label: Literal["food", "service", "price", "unclear"]


load_dotenv(find_dotenv())
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is not set — check your .env file")

client = OpenAI()

for review in REVIEWS:
    response = client.responses.parse(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=review,
        text_format=ReviewLabel,
    )
    result = response.output_parsed
    if result is None:
        print(f"{'NO PARSE':10} <- {review}")
        continue
    print(f"{result.label:10} <- {review}")
    print(f"{'':10}    reason: {result.reason}")
