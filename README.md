# wardrobe-ai

Take inventory of your wardrobe, using an LLM to visually identify its characteristics,
then use those findings to build an outfit.

## Why
You might have a lot of clothes, and because of that, an exponential combination of possible outfits.
All those ideas won't come to you. AI can help out with that, but it can't efficiently handle all of those pictures.
This app tags your clothes with text descriptors, making it more efficient for AI to come up with an outfit based on what's in your wardrobe and based on whatever occasion you're dressing up for.

## What it does (current status)
TBD

## How it works
TBD

## Setup
1. git clone …
2. uv sync
3. Copy .env.example to .env and add your ANTHROPIC_API_KEY
4. uv run wardrobe-ai add photo1.jpg photo2.jpg

## Tech
Python 3.13, uv, Anthropic API, Pydantic, SQLite
