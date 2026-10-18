# wardrobe-ai

Take inventory of your wardrobe, using an LLM to visually identify its characteristics.

## Why
You might have a lot of clothes, and because of that, an exponential combination of possible outfits.
All those ideas won't come to you. AI can help out with that, but it can't efficiently handle all of those pictures.
This app tags your clothes with text descriptors, making it more efficient for AI to come up with an outfit based on what's in your wardrobe and based on whatever occasion you're dressing up for.

## Setup

**You need:** [uv](https://docs.astral.sh/uv/) and an Anthropic API key
(create one at https://console.anthropic.com; API usage is billed separately
from a Claude chat subscription). Commands below are for macOS, Linux, or WSL.

1. Install uv (skip if you have it):
   `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Clone and install:

git clone https://github.com/gtun/wardrobe-ai.git
cd wardrobe-ai
uv sync

3. Add your key: `cp .env.example .env`, then edit `.env`.

## Try it

No API key yet? Test mode runs everything except the AI call:

    uv run wardrobe-ai add -t tests/fixtures/*.jpg

With a key, tag the sample jacket for real:

    uv run wardrobe-ai add tests/fixtures/*.jpg -p "nonnative x Undercover blouson"

Each run prints the new garment ID. Results are saved in `data/wardrobe.db`,
photos in `data/garments/<id>/`, and every tagging call (with token usage)
in `data/tagging_log.jsonl`. Add `-v` for debug output.

## Upcoming features
An outfit command to ask the LLM to create an outfit for you based on what's already in your warderobe.

## How it works
TBD

## Setup
1. git clone …
2. uv sync
3. Copy .env.example to .env and add your ANTHROPIC_API_KEY
4. uv run wardrobe-ai add photo1.jpg photo2.jpg

## Tech
Python 3.13, uv, Anthropic API, Pydantic, SQLite
