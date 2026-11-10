# enclothed

A wardrobe you can talk to. Photograph your clothes once, and enclothed uses an LLM to turn each garment into a structured, searchable record. From there it suggests outfits for whatever you're dressing for, answers questions about your closet, and keeps track of what you've put together.

It runs as a web app (phone or desktop) with a command-line interface alongside it. It's live at [enclothe.me](https://enclothe.me), where sign-in is by invitation, and you can run your own copy with your own Anthropic API key.

## Why

If you own a lot of clothes, you have a huge number of possible outfits, and most of them will never occur to you. A chat assistant can help, but only for a moment: it can't keep track of hundreds of photos, and it forgets your wardrobe as soon as the conversation ends.

enclothed looks at each photo once, writes down what it sees (category, colors, fabric, fit, formality, warmth and more), and stores that in a database. Outfit requests and questions after that work from the text records alone, so they're fast, cheap, and always based on what you actually own.

## What it does

- **Add garments from photos.** Snap the front, back, and labels with your phone. The AI tags the garment, reads the care and brand labels (translating Japanese, Chinese and other languages), and files each photo by role. You review every field before it's saved, with a one-tap **Accept all**.
- **Get outfit suggestions.** Describe the occasion and the weather ("17°C, burger and beer lunch with a former coworker") and get 2–4 outfits built from your wardrobe. Pick anchor pieces you want to wear, or put an outfit together yourself. Every suggestion is saved, and you can like or dislike it.
- **Recreate a look.** Photograph an outfit you like (a lookbook shot, a store mannequin, a street snap) and get up to two recreations from your own wardrobe, with the garment standing in for each piece, how close it is, and what you don't have.
- **Ask your wardrobe.** A chat pop-up on every page answers questions like "what's my color spread?" or "which jackets have I never worn in an outfit?" It answers with a number, a list, a table, or garment photos, whichever fits, and can show how it worked the answer out.
- **Fix and fill in details.** Click any field to correct it. **Mend** asks the AI to fill in only the blank fields from the saved photos, and never overwrites anything you've set.
- **Describe your style once.** Write your tastes and needs (loose fits, never shorts, glasses with everything); the AI can tidy it into a clear brief, and it's sent with every outfit request.
- **Group sets and retire garments.** Link a suit jacket and trousers as a set. Garments you no longer own are marked disowned rather than deleted, so your outfit history stays intact.
- **See what it costs.** A usage page shows estimated AI spend over time, by type of call and model. Everyone sees their own; admins see everyone's.
- **Multiple people, multiple languages.** Each person has their own wardrobe and chooses English, Traditional Chinese (Taiwan), or Japanese. Admins can switch into anyone's wardrobe to help or debug. A shared demo wardrobe resets daily so new people can try things without their own clothes in it.

## How it works

```
photos ──► vision model (once) ──► structured record ──► SQLite
                                                           │
            outfit requests, questions  ◄──────────────────┘
            (text only, no photos)

saved photos ──► mend (on request) ──► blank fields filled in
```

A few design decisions shape the whole app:

- **Look at each image once.** Intake sends a garment's photos to Claude a single time and gets back a validated [Pydantic](https://docs.pydantic.dev/) model. Outfit suggestions and questions run on text only, which keeps them small and cheap. The one exception is mend, which you run on purpose: it sends a garment's saved photos again to fill in fields that are still blank.
- **Review before saving.** A wrong tag spoils every outfit that uses it, so new garments and mended fields go through a field-by-field review.
- **Rules in code, taste in the LLM.** Fixed vocabularies (categories, colors, fabrics, fit, formality, warmth…) are enforced in code, and the LLM's outfit suggestions are validated against the real wardrobe before they're shown or saved. The LLM handles judgment: what looks good together and why.
- **Questions run in a sandbox.** "Ask your wardrobe" lets the LLM write SQL, but only read-only queries against a throwaway, in-memory copy of one person's data, with private notes removed and time and size limits on every query.
- **Every AI call is metered.** All LLM calls go through one module, which logs token usage (including prompt-cache reads and writes) and estimated cost. The wardrobe is prompt-cached for 5 minutes, so back-to-back outfit requests use far fewer input tokens.

## Run it locally

**You need:** [uv](https://docs.astral.sh/uv/) and an Anthropic API key (create one at https://console.anthropic.com; API usage is billed separately from a Claude chat subscription). Commands are for macOS, Linux, or WSL.

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

3. Configure: `cp .env.example .env`, then edit `.env`:

   ```bash
   ANTHROPIC_API_KEY=your-key-here
   ENCLOTHED_DEV_USER=owner    # local only: signs you in as the first user, no login
   ```

   Never set `ENCLOTHED_DEV_USER` on a public server.

4. Start the web app:

   ```bash
   uv run fastapi dev src/enclothed/api.py
   ```

   Open http://localhost:8000. The interactive API docs are at http://localhost:8000/docs.

The database is created on first run at `data/enclothed.db`, with migrations applied automatically. Photos go in `data/garments/<id>/` and thumbnails in `data/thumbs/`. Uploaded photos are turned upright, converted to JPEG, and resized to at most 2000 px, so phone photos (including iPhone HEIC) fit the API's limits.

### Try it without an API key

Test mode runs everything except the AI call, using the sample jacket photos in `tests/fixtures/`:

```bash
uv run enclothed add -t tests/fixtures/*.jpg
uv run enclothed list
uv run enclothed outfit -t -p "autumn walk in the city"
uv run enclothed mimic -t                  # matches a built-in sample look
```

## Using the web app

- **Wardrobe:** every garment by category, in Grid, Large, or List view, with filters for sets and for garments not in any outfit. **+ Add garment** opens the camera or photo library, with a box for details the photos can't show (the true color, the name) and one for private notes that are never sent to the AI. Cancelling the review discards the garment and its photos.
- **Garment page:** photos, its set, every outfit it's in, and what it's most often paired with. Click any detail or the styling notes to edit. Fixed lists use a type-to-filter dropdown that only accepts listed values. If you change a color the styling notes mention, the page highlights the mention and offers to update it.
- **Outfits:** every outfit, grouped by request, filterable by request text, date, formality (of the least formal piece) and warmth (of the warmest top layer). **+ New outfit** opens the builder: add pieces, describe the occasion, then **Generate outfit suggestions** or **Save as my own outfit**. Disliked outfits are hidden unless you turn on "Show disliked".
- **Looks:** from Outfits, **Mimic a look** takes photos of one outfit. The AI reads the photos once, breaking the look into its pieces with the same fields your garments have, then matches them to your wardrobe as text. A look's page shows each piece beside the garment standing in for it (exact, close, loose, or not owned). Each recreation is saved as an outfit.
- **Style:** your saved style brief, sent with every outfit request from the web and the CLI.
- **Ask your wardrobe:** the pop-up in the corner of every page. The conversation lives in the browser, so a refresh clears it.
- **Usage:** estimated AI cost over time. Prices live in `MODEL_PRICES` in `src/enclothed/config.py`.
- **Help:** each page explains itself the first time you visit, and **?** brings that back.

Garment and set ID numbers appear only for admins; everyone else knows a garment by its brand, color, and photo.

## Command line

The CLI works on the same database as the web app.

| Command | What it does |
|---|---|
| `add <photos…>` | Tags a garment from local photo paths or URLs (quote URLs) and saves it |
| `list` | Lists garments, grouped by category |
| `outfit` | Gets 2–4 outfit suggestions from a request, anchor pieces, or both |
| `mimic <photos…>` | Recreates the look in one or more photos (paths or URLs) from your wardrobe |
| `set` | Groups two or more garments into a set, like a two-piece suit |
| `mend [ids…]` | Fills blank fields from saved photos, without review; never overwrites a value |
| `users` | Lists everyone who can sign in |
| `adduser <username> <email>` | Adds a person who can sign in |
| `edituser <id>` | Changes a user's username, email, or language |
| `demo-seed` | Rebuilds the shared demo wardrobe from a sample of yours |

Examples:

```bash
uv run enclothed add photos/*.jpg -p "nonnative x Undercover blouson" -n "bought in Osaka"
uv run enclothed list -c jeans -c chinos
uv run enclothed outfit -p "17 degrees celsius, burger and beer lunch with a friend"
uv run enclothed outfit -w 1 18            # outfits that include garments 1 and 18
uv run enclothed mimic lookbook.jpg -p "the jacket is the point"
uv run enclothed set -n "navy suit" -g 12 13
uv run enclothed mend -l 5                 # try a small batch first
uv run enclothed adduser alex alex@example.com -l zh-TW
```

Options:

- `add`: `-t` test mode (no AI call); `-p` details you know, which take priority over what the AI sees; `-n` private notes, never sent to the AI
- `list`: `-c NAME` a category (`outerwear`) or subcategory (`jeans`); repeat to combine
- `outfit`: `-p` the occasion, weather, or anything else; `-w ID…` anchor pieces; `-t` test mode; `--no-cache` skip prompt caching (the first cached call costs about 25% more on the wardrobe, and the savings start with the second)
- `mimic`: `-p` a note about the look, such as what matters most or what to leave out; `-t` test mode; `--no-cache` as for `outfit`
- `set`: `-g ID…` the garments (at least two, required); `-n` an optional name
- `mend`: `-l N` stop after N garments; `-r` include garments mend already tried; `-u ID` mend someone else's wardrobe
- `adduser`: `--admin` lets them switch between wardrobes; `-l` their language (`en-US`, `zh-TW`, `ja-JP`)
- `edituser`: `-u` username, `-e` email, `-l` language
- `demo-seed`: `--per-category N` (default 5), `--outfits N` (default 8)

Every command accepts `-v` / `--verbose` for debug output.

## Accounts and sign-in

Each person has their own wardrobe. The first user, `owner`, is created with the database and is an admin. Admins can switch into anyone's wardrobe from the bar at the top of the page, and a banner shows whose wardrobe you're viewing.

On a server, sign-in is handled by [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/): people log in with a one-time code emailed to them, and enclothed verifies the signed token Cloudflare adds to each request, then looks up the user by email. Set `ACCESS_TEAM_NAME` and `AUD_TAG` in `.env`, and add each person with `adduser`. Any failure to verify is an error, never a fallback to a default user.

### Demo wardrobe

Anyone signed in can open a shared demo wardrobe and add garments or use the AI there. It's a sample of the owner's wardrobe without private notes, style notes, or the wording of past requests. It rebuilds itself on the first visit after 8:00 UTC each day, and AI use in it stops at `DEMO_DAILY_TOKEN_LIMIT` in `config.py`. Create it or refresh the sample with `enclothed demo-seed`; don't edit `data/demo-template/` by hand.

### Languages

The language menu changes the names of fixed terms (colors, categories, fabrics, fit…), the date format, and the language the AI writes in from then on. Buttons and headings stay in English, and saved notes and outfits aren't retranslated. The database always stores fixed terms in English; translations live in `src/enclothed/locales/`.

## Running with Docker

```bash
docker build -t enclothed .
docker run -d --name enclothed --restart unless-stopped \
  -p 127.0.0.1:8000:8000 --env-file .env -v "$PWD/data:/app/data" enclothed
```

All state lives in the mounted `data/` folder, so back that up. The container listens only on `127.0.0.1:8000`; put a reverse proxy or tunnel in front of it for HTTPS and sign-in.

Maintenance commands:

| Command | What it does |
|---|---|
| `uv run snapshot` | Writes a consistent copy of the database to `data/snapshots/`, keeping 7 daily and 4 weekly |
| `scripts/mend-all.sh` | Backs up the database, mends 5 garments, and asks before mending the rest |
| `uv run backup` / `restore` / `refresh` | Local development: save `data/` as a golden copy, put it back, or wipe it |

## Customizing

The front end is plain HTML, CSS, and JavaScript in `public/`, with no build step: edit a file and refresh.

| To change | Edit |
|---|---|
| Colors and fonts (Day and Evening themes) | `public/css/theme.css` |
| Spacing, sizes, layout | `public/css/app.css` |
| Date formats and the AI-button color source | `public/js/settings.js` |
| Text or layout on a page | the matching file in `public/js/templates/` |
| Words for fixed terms in each language | `src/enclothed/locales/` |
| Models, token caps, demo limits, prices | `src/enclothed/config.py` |
| The site icon | `public/icons/` |

Buttons that call the AI (and spend tokens) share the class `llm-action` and their own color, `--llm`. By default that color comes from your wardrobe: the most common colorful accent among light garments for Day, and among dark garments for Evening.

## Project layout

```
src/enclothed/
  api.py           FastAPI app: REST endpoints and the static front end
  main.py          CLI entry point
  llm.py           every Anthropic API call, with token and cost logging
  intake.py        photo tagging          mend.py      filling blank fields
  outfit.py        suggestions and validation
  weigh.py         "should I get this?"   mimic.py     recreating a photographed look
  similarity.py    shortlisting garments that look alike on paper
  insights.py      "Ask your wardrobe"    sandbox.py   read-only query copy
  auth.py          Cloudflare Access sign-in and acting as another user
  db.py            SQLite access          schema.sql   base schema
  models.py        Pydantic models        fabrics.py   the fixed fabric list
  i18n.py, locales/  translations         demo.py      the demo wardrobe
  photos.py        orientation, resizing, thumbnails
migrations/        numbered SQL migrations, applied on start-up
public/            the web front end (core helpers, features, page templates)
tests/             pytest suite
```

## Tests

```bash
uv run pytest
```

GitHub Actions runs the suite on every pull request and push to `main`, and it must pass before merging.

## Roadmap

- "Should I buy this?": photograph an item while shopping and see how it fits your wardrobe, what it duplicates, and what outfits it unlocks
- Charts in "Ask your wardrobe" answers
- Configurable LLM key and model, with support for other providers
- Logging when you actually wear an outfit
- Style modes, such as Western tailored versus silhouette-based styling

## Tech

Python 3.13, uv, FastAPI, Pydantic, SQLite, Anthropic API (Claude), Pillow, PyJWT, vanilla JavaScript, pytest, Docker, GitHub Actions, Cloudflare Access

## About

enclothed started as my [Boot.dev](https://www.boot.dev) Personal Project 1, a command-line tool for tagging photos and suggesting outfits, and grew from there into a hosted, multi-user web app.
