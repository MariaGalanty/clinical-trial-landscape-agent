# Imports for load_dotenv and OpenAI.
# A call to load_dotenv() before creating the client.
# A client.responses.create(...) call with the model you chose and a toy question.
# Print response.output_text.
# Print response.usage.


import os
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

MODEL = "gpt-5.4-nano"
# Load the .env file
load_dotenv(find_dotenv())
# Access the OpenAI API key from the environment variable
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set — check your .env file")


client = OpenAI()  # finds OPENAI_API_KEY in the environment
response = client.responses.create(
    model=MODEL,
    # instructions=
    input="Name one fruit that is yellow. Answer in one word.",
)
print(response.output_text)  # e.g. "Banana"
print(response.usage)
