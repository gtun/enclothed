"""eval-previews: edit garments' photos with an image model, to see whether garment previews (#74) look right.

Each garment's photo goes to the image model as Rework sends it (reworks.source_photo) with the instruction,
and nothing from its record. This writes nothing to the wardrobe. It writes one folder per run under
data/evals/previews/:

    index.html     each garment's photo beside its previews, with the instruction, model and cost: open it in a browser
    results.jsonl  one line per garment and repeat: the files, tokens and any error
    <id>_photo.*   the photo that was sent
    <id>_<run>.png each preview

Previews always use OpenAI, whatever provider the app is set to, so OPENAI_API_KEY has to be set. They're priced
by token like the text models, but output tokens cost $30 per million, so a preview is cents, not fractions of one.

Usage:
    uv run eval-previews --label blue --ids 14 22 -i "Make it bright blue"
    uv run eval-previews --label blue-flare --ids 14 -i "Make it bright blue" --model gpt-image-2.6-flare
    uv run eval-previews --label cropped --ids 31 -i "Crop the hem to the waist" --quality high --runs 2
    uv run eval-previews --label smoke --ids 14 -i "Make it bright blue" --test   # grey placeholders, no tokens
"""
import argparse
import html
import io
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps

from enclothed import config, db, photos
from enclothed.llm import Client, NotConfigured, ServiceError, UnusableResponse, make_client, preview_garment
from enclothed.models import Garment, ImageUsage
from enclothed.reworks import source_photo
from enclothed.tag_evals import choose_garments
from enclothed.usage import image_call_cost

PREVIEW_EVALS_DIR = config.DATA_DIR / "evals" / "previews"
QUALITIES = ["low", "medium", "high", "xhigh", "max", "auto"]


def placeholder_preview(photo: Path) -> bytes:
    """Test mode's preview: the photo in grey, so the page shows something without a call."""
    with Image.open(photo) as image:
        grey = ImageOps.grayscale(ImageOps.exif_transpose(image))
    out = io.BytesIO()
    grey.save(out, "PNG")
    return out.getvalue()


def total_cost(rows: list[dict]) -> float | None:
    costs = [image_call_cost(ImageUsage.model_validate(row["usage"])) for row in rows if row["usage"]]
    priced = [cost for cost in costs if cost is not None]
    return sum(priced) if priced else None


def write_page(path: Path, label: str, instruction: str, model: str, quality: str, rows: list[dict]) -> None:
    """One row per garment: the photo sent, then each preview or why it failed. Plain HTML with no scripts, opened
    from the run's folder, so the images are relative paths."""
    e = html.escape
    cost = total_cost(rows)
    by_garment: dict[int, list[dict]] = {}
    for row in rows:
        by_garment.setdefault(row["garment_id"], []).append(row)
    sections = []
    for garment_rows in by_garment.values():
        first = garment_rows[0]
        cells = [f'<figure><img src="{e(first["photo"])}" alt=""><figcaption>Photo sent</figcaption></figure>']
        for row in garment_rows:
            if row["error"]:
                cells.append(f'<figure class="failed"><figcaption>Run {row["run"]} failed: {e(row["error"])}</figcaption></figure>')
                continue
            call = image_call_cost(ImageUsage.model_validate(row["usage"])) if row["usage"] else None
            caption = f'Run {row["run"]}' + (f", about ${call:.3f}" if call is not None else "")
            cells.append(f'<figure><img src="{e(row["preview"])}" alt=""><figcaption>{e(caption)}</figcaption></figure>')
        sections.append(f'<section><h2>#{first["garment_id"]} {e(first["name"])}</h2><div class="row">{"".join(cells)}</div></section>')
    summary = f"<code>{e(model)}</code>, quality {e(quality)}, {len(rows)} calls" + (f", about ${cost:.3f}" if cost is not None else "")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Preview eval: {e(label)}</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 24px; background: #fafafa; color: #222; }}
  .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  figure {{ margin: 0; width: 320px; }}
  img {{ width: 100%; height: auto; border: 1px solid #ddd; background: #fff; }}
  .failed {{ color: #a00; }}
</style></head><body>
<h1>Preview eval: {e(label)}</h1>
<p><strong>Instruction:</strong> {e(instruction)}</p>
<p>{summary}</p>
{"".join(sections)}
</body></html>
"""
    path.write_text(page, encoding="utf-8")


def run(label: str, instruction: str, runs: int, user_id: int, db_path: Path, ids: list[int] | None, limit: int,
        is_test: bool, out_root: Path, quality: str = config.PREVIEW_QUALITY) -> Path:
    if db.select_user(db_path, user_id) is None:
        raise ValueError(f"No user {user_id} in {db_path}")
    chosen: list[Garment] = choose_garments(db.select_owned_garments(db_path, user_id), ids, limit)
    if not chosen:
        raise ValueError(f"User {user_id} has no garments with photos")
    model = config.PREVIEW_MODEL
    client: Client | None = None if is_test else make_client("openai")

    out_dir = out_root / f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{label}"
    out_dir.mkdir(parents=True)
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as scratch:
        for number, garment in enumerate(chosen, start=1):
            source = source_photo(photos.get_photo_paths(garment.id))
            sendable = photos.sendable_copies([source], Path(scratch))[0]
            sent = out_dir / f"{garment.id}_photo{sendable.suffix.lower()}"
            shutil.copyfile(sendable, sent)
            for repeat in range(1, runs + 1):
                print(f"[{number}/{len(chosen)}] #{garment.id} {garment.name} run {repeat}/{runs}…", file=sys.stderr, flush=True)
                row = {"garment_id": garment.id, "name": garment.name, "run": repeat, "label": label,
                       "instruction": instruction, "model": model, "quality": quality, "photo": sent.name,
                       "preview": None, "usage": None, "error": None}
                try:
                    if client is None:
                        image, usage = placeholder_preview(sent), None
                    else:
                        image, usage = preview_garment(client, sent, instruction, quality)
                except (ServiceError, UnusableResponse, OSError) as error:   # one bad garment shouldn't stop the run
                    row["error"] = f"{getattr(error, 'kind', type(error).__name__)}: {error}"
                    if isinstance(error, UnusableResponse):   # it answered, so its tokens count toward the cost
                        row["usage"] = error.usage.model_dump()
                else:
                    preview = out_dir / f"{garment.id}_{repeat}.png"
                    preview.write_bytes(image)
                    row["preview"] = preview.name
                    row["usage"] = usage.model_dump() if usage else None
                rows.append(row)
                with (out_dir / "results.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_page(out_dir / "index.html", label, instruction, model, quality, rows)
    cost = total_cost(rows)
    failed = sum(1 for r in rows if r["error"])
    print(f"\n{len(rows)} calls, {failed} failed" + (f", about ${cost:.3f}." if cost is not None else "."))
    print(f"Open it: {out_dir / 'index.html'}")
    return out_dir


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="eval-previews", description="Edit garments' photos with an image model and show the results side by side.")
    parser.add_argument("-l", "--label", required=True, help="Name for this run, e.g. blue (used in the folder name)")
    parser.add_argument("-i", "--instruction", required=True, help='The change to make, e.g. "Make it bright blue"')
    parser.add_argument("--ids", type=int, nargs="+", metavar="ID", help="Preview these garments only")
    parser.add_argument("--limit", type=int, default=3, help="How many garments, spread across categories, when there are no --ids (default 3)")
    parser.add_argument("--runs", type=int, default=1, help="How many previews of each garment (default 1)")
    parser.add_argument("--user", type=int, default=config.DEFAULT_USER_ID, help="Whose wardrobe (default: the owner)")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="Database to read (default: the app's). Nothing is written to it")
    parser.add_argument("-m", "--model", help=f"Image model instead of {config.PREVIEW_MODEL}, e.g. {', '.join(m for m in config.IMAGE_MODEL_PRICES if m != config.PREVIEW_MODEL)}")
    parser.add_argument("-q", "--quality", choices=QUALITIES, default=config.PREVIEW_QUALITY, help=f"Output quality (default {config.PREVIEW_QUALITY}). Higher costs more")
    parser.add_argument("-t", "--test", action="store_true", help="Grey placeholders instead of previews: checks the script, spends no tokens")
    args = parser.parse_args()
    if args.runs < 1 or args.limit < 1:
        parser.error("--runs and --limit must be at least 1")
    if not all(c.isalnum() or c in "-_." for c in args.label):
        parser.error("--label may only use letters, digits, - _ and .")
    if not args.instruction.strip():
        parser.error("--instruction can't be blank")
    if args.model:
        config.PREVIEW_MODEL = args.model   # this run only: llm reads it at each call
        if args.model not in config.IMAGE_MODEL_PRICES:
            print(f"{args.model} has no price in config.IMAGE_MODEL_PRICES, so costs won't show.", file=sys.stderr)
    try:
        run(args.label, args.instruction.strip(), args.runs, args.user, args.db, args.ids, args.limit, args.test,
            PREVIEW_EVALS_DIR, args.quality)
    except (ValueError, NotConfigured) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
