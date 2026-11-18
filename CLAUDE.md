# enclothed

## Commands
- Use uv for everything: `uv sync`, `uv run ...`. Don't use pip or activate a venv by hand.
- Add dependencies with `uv add`, never by editing `pyproject.toml`. CI runs `uv sync --locked`
  and fails if `uv.lock` is out of date.
- Run `uv run pytest` before saying a step is done.
- Never make real API calls to check your work. CLI commands take `-t` to skip them, e.g.
  `uv run enclothed outfit -t -p "..."`.
- To run the app: `uv run fastapi dev src/enclothed/api.py`. Without `ENCLOTHED_DEV_USER=owner`
  in `.env`, every request fails sign-in.

## Where code goes
- Keep `api.py` to HTTP. Put SQL in `db.py`, build response models in `responses.py`, handle
  photo files in `photos.py`, and put feature logic in its own module (like `shares.py`).
- Make Anthropic calls only through `llm.py`, so token usage is logged.
- For a schema change, add the next numbered file in `migrations/` AND make the same change in
  `src/enclothed/schema.sql`. A fresh database runs only schema.sql. Never edit a merged migration.

## Rules
- When a db function or endpoint reads or changes wardrobe data, take the signed-in user's
  `user_id` and filter by it. Another user's item gets a 404, not a 403.
- Save fixed terms (colors, categories, fabrics) in English. Translate only for display, using `locales/`.
- Use each module's `logger`, not `print`, outside the CLI. Never log API keys or share tokens.

## Front end (`public/`)
- No `import`/`export`, npm or build step: files are plain scripts sharing one global scope.
  When you add a JS file, add its `<script>` tag to `index.html`.
- `share.html` (the public share page) loads its own short list of scripts, including some shared
  templates. When you change a file it loads, don't make it call anything `share.html` doesn't load.
- Put page text and markup in `js/templates/` and behavior in `js/features/`. Use the CSS
  variables from `css/theme.css` and never hard-code colors or fonts, or Evening mode breaks.
- There are no front-end tests. After a UI change, list what to click to check it.

## Tests
- Add or update tests in `tests/test_<module>.py` for every Python change.
- In tests, replace LLM functions with fakes via `monkeypatch`, as `tests/test_api.py` does.
- Use `tmp_path` for every file and database. Never read or write `data/`.

## Working style
- Make one small, reviewable change, then stop for review before the next.
- Never commit to `main` or merge a PR. Work on a branch and open a PR.
- Explain non-obvious choices in the PR description.
- Don't deploy or touch the server.
