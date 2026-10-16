import os
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

MODEL = "gpt-5.4-nano"

INSTRUCTIONS = """You classify restaurant reviews by their main complaint or praise.
Allowed labels:
- food: taste, quality, or temperature of the food
- service: staff, waiting time, or friendliness
- price: cost or value for money
- unclear: too vague to classify
Reply with the label only."""

REVIEWS = [
    "The pasta was cold and bland.",
    "Our waiter ignored us for 20 minutes.",
    "Way too expensive for such small portions.",
    "It was fine I guess.",
    "Lovely staff, but the steak was overcooked.",
]

load_dotenv(find_dotenv())
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is not set — check your .env file")

client = OpenAI()

for review in REVIEWS:
    response = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=review,
    )
    print(f"{response.output_text!r:12} <- {review}")
