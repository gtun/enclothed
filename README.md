# enclothed

Take inventory of your wardrobe, using an LLM to visually identify its characteristics.

## Why

You might have a lot of clothes, and because of that, a huge number of possible outfits.
All those ideas won't come to you. AI can help out with that, but it can't efficiently handle all of those pictures.
This app tags your clothes with text descriptors, making it more efficient for AI to come up with an outfit based on what's in your wardrobe and whatever occasion you're dressing up for.

## Setup

**You need:** [uv](https://docs.astral.sh/uv/) and an Anthropic API key
(create one at https://console.anthropic.com; API usage is billed separately
from a Claude chat subscription). Commands below are for macOS, Linux, or WSL.

1. Install uv (skip if you have it):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and install:

   ```bash
   git clone https://github.com/gtun/enclothed.git
   cd enclothed
   uv sync
   ```

3. Add your key: `cp .env.example .env`, then edit `.env`.

## Try it

No API key yet? Test mode runs everything except the AI call:

```bash
uv run enclothed add -t tests/fixtures/*.jpg
```

With a key, tag the sample jacket for real:

```bash
uv run enclothed add tests/fixtures/*.jpg -p "nonnative x Undercover blouson"
```

Each run prints the new garment ID. Then see what's in your wardrobe:

```bash
uv run enclothed list
```

Results are saved in `data/wardrobe.db`, photos in `data/garments/<id>/`, and
every tagging call (with token usage) in `data/tagging_log.jsonl`.

Ask for an outfit recommendation. Test it with:

```bash
uv run enclothed outfit -t -p "autumn walk in the city"
```

Or, once your wardrobe is filled out, with a real request to the LLM:

```bash
uv run enclothed outfit -p "17 degrees celsius. Out for a burger and beer lunch with friend and former coworker"
```

You can also build an outfit anchored around specific garments in your wardrobe based on their IDs:

```bash
uv run enclothed outfit -w 1 18
```

Group multiple garments together into a set, like a two piece suit, optionally with a name:

```bash
uv run enclothed set -n "navy suit" -g 12 13
```

## Commands

| Command | What it does |
|---|---|
| `add <photos…>` | Tags a garment from one or more local photo paths or URLs (quote URLs) and saves it |
| `list` | Lists all garments, grouped by category |
| `outfit` | Gets 2-4 outfit recommendations from the LLM based on a request or anchor pieces |
| `set` | Groups two or more garments into a set, like a two-piece suit |

Options for `add`:

- `-t`, `--test`: skip the AI call and save a sample garment (no API key needed)
- `-p`, `--prompt-message TEXT`: details you know about the garment (name, true color, fit); these take priority over what the AI sees in the photos
- `-n`, `--notes TEXT`: your own notes, saved as-is and never sent to the AI

Options for `list`:

- `-c`, `--category NAME`: show only this category (e.g. `outerwear`) or subcategory (e.g. `jeans`); repeat to combine, e.g. `-c jeans -c chinos`

Options for `outfit`:

- `-p`, `--prompt-message`: have a special occasion? Weather getting kind of chilly? Specify it here so the LLM can tailor the outfit to your needs.
- `-w`, `--with`: add an anchor piece, or multiple, by its ID, and the suggested outfits will include them

Options for `set`:

- `-g`, `--garment-ids ID [ID ...]`: the garments in the set (at least two, required)
- `-n`, `--name TEXT`: an optional name for the set

Every command accepts `-v`, `--verbose` for debug output.

## How it works

1. Give the `add` command URLs or paths of photos of one garment.
2. Photos are staged, and Claude tags them once into a structured Pydantic model, including a role for each photo (front, back, label, detail).
3. The record is saved in SQLite, the call is logged with its token usage, and the photos are filed by role.
4. Everything after intake works from the text records, so the photos never need to be sent again.

## Tests

```bash
uv run pytest
```

## Upcoming features

- A way to review and edit a garment's tags in case the LLM got something wrong.
- A UI to browse all garments in your wardrobe.

## Tech

Python 3.13, uv, Anthropic API, Pydantic, SQLite, pytest
