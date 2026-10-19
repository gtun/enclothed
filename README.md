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

```bash
   git clone https://github.com/gtun/wardrobe-ai.git
   cd wardrobe-ai
   uv sync
```

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
An outfit command to ask the LLM to create an outfit for you based on what's already in your wardrobe.
A UI to show all garments in your wardrobe, and make any edits as necessary in case the LLM's tagging was off.

## How it works

1. Give it URLs or paths of photos of a garment with the add command
2. Photos are staged, and Claude tags them once into a structured Pydantic model.
3. The record is saved in SQLite and the photos are filed by role.

## Tech
Python 3.13, uv, Anthropic API, Pydantic, SQLite
