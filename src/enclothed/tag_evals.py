"""eval-tags: re-tag garments already in the wardrobe and compare each field with the saved record.

The saved record is the reference: it's what the owner reviewed and kept. Re-tagging writes nothing to the
wardrobe. It writes one folder per run under data/evals/tags/:

    results.jsonl  one line per garment and repeat: the saved and tagged fields, how each compared, tokens
    scores.md      the match rate for each field, then each garment's differences and both styling notes

Fixed fields are compared exactly, colors as sets, formality and warmth both exactly and within one step,
brand and country of origin ignoring case, materials by fiber and percent. Photo roles are compared with the
role in each saved photo's file name. Free text (styling notes, style tags, pattern) is shown, not scored.

Usage:
    uv run eval-tags --label sonnet-tags                      # 12 garments, spread across categories
    uv run eval-tags --label terra-tags --provider openai
    uv run eval-tags --label terra-original --provider openai --image-detail original
    uv run eval-tags --label labels --ids 14 22 56            # these garments only
    uv run eval-tags --label smoke --test                     # canned tags, no tokens

On the server: docker exec enclothed /app/.venv/bin/eval-tags --label ...
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from enclothed import config, db, photos
from enclothed.evals import total_cost
from enclothed.intake import tag_photos
from enclothed.llm import PROVIDER_VARIABLE, ServiceError, UnusableResponse, active_provider, make_client, model_for
from enclothed.models import Garment, TaggingResult
from enclothed.usage import call_cost

TAG_EVALS_DIR = config.DATA_DIR / "evals" / "tags"
DEFAULT_LIMIT = 12

EXACT_FIELDS = ["category", "subcategory", "primary_color", "fit", "sheen", "fabric_type", "shape", "hem",
                "fabric_weight", "sleeve", "statement"]
SET_FIELDS = ["secondary_colors", "accent_colors"]
STEP_FIELDS = ["formality", "warmth"]           # scored exactly, and again as within one step
TEXT_FIELDS = ["brand", "country_of_origin"]    # ignoring case and spacing
SCORED_FIELDS = EXACT_FIELDS + SET_FIELDS + STEP_FIELDS + TEXT_FIELDS + ["materials"]
SHOWN_FIELDS = ["pattern", "style_tags", "styling_notes", "label_text"]

MATCH, DIFFER, SAVED_BLANK = "match", "differ", "saved blank"


# --- choosing garments ----------------------------------------------------------------------

def choose_garments(garments: list[Garment], ids: list[int] | None, limit: int) -> list[Garment]:
    """The named garments, or up to limit with photos, taken a category at a time so every category shows up."""
    with_photos = [g for g in garments if photos.get_photo_paths(g.id)]
    if ids:
        by_id = {g.id: g for g in with_photos}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise ValueError(f"No owned garment with photos has id {missing}")
        return [by_id[i] for i in ids]
    by_category: dict[str, list[Garment]] = {}
    for garment in sorted(with_photos, key=lambda g: g.id):
        by_category.setdefault(garment.category, []).append(garment)
    spread = [g for row in zip_longest(*by_category.values()) for g in row if g is not None]
    return spread[:limit]


def saved_roles(paths: list[Path]) -> list[str]:
    """Each photo's role, from the start of its saved file name (front_00.jpg)."""
    return [p.name.split("_")[0] if p.name.split("_")[0] in photos.ROLES else "other" for p in paths]


# --- comparing ------------------------------------------------------------------------------

def _text(value: str | None) -> str | None:
    return " ".join(value.casefold().split()) if value else None


def _fibers(materials: list[Any]) -> list[tuple[str, int]] | None:
    """Every fiber and its percent, whichever part it's in, so "shell: wool 80%" and "wool 80%" agree."""
    fibers = sorted((_text(f["fiber"]), f["percent"]) for part in materials for f in part["fibers"])
    return fibers or None


def compare(saved: Garment, tagged: Garment) -> dict[str, str]:
    """match, differ, or saved blank for each scored field. A saved blank isn't counted: there's nothing to
    check against. A field the re-tag left blank but the record fills is a difference."""
    a, b = saved.model_dump(mode="json"), tagged.model_dump(mode="json")
    pairs = {field: (a[field], b[field]) for field in EXACT_FIELDS + STEP_FIELDS}
    pairs |= {field: (sorted(a[field]) or None, sorted(b[field]) or None) for field in SET_FIELDS}
    pairs |= {field: (_text(a[field]), _text(b[field])) for field in TEXT_FIELDS}
    pairs["materials"] = (_fibers(a["materials"]), _fibers(b["materials"]))
    results = {field: SAVED_BLANK if mine is None else MATCH if mine == theirs else DIFFER
               for field, (mine, theirs) in pairs.items()}
    for field in STEP_FIELDS:
        mine, theirs = a[field], b[field]
        results[f"{field} ±1"] = SAVED_BLANK if mine is None else MATCH if theirs is not None and abs(mine - theirs) <= 1 else DIFFER
    return results


def role_matches(expected: list[str], result: TaggingResult) -> int:
    """How many photos got back the role they're saved under."""
    got = {tag.index: tag.role for tag in result.photos}
    return sum(1 for index, role in enumerate(expected) if got.get(index) == role)


# --- the run --------------------------------------------------------------------------------

def field_rates(rows: list[dict]) -> list[tuple[str, int, int]]:
    """(field, matched, compared) for each scored field, in a fixed order."""
    fields = next((list(r["fields"]) for r in rows if r["fields"]), [])
    out = []
    for field in fields:
        compared = [r["fields"][field] for r in rows if r["fields"] and r["fields"][field] != SAVED_BLANK]
        out.append((field, compared.count(MATCH), len(compared)))
    return out


def _shown(value: Any) -> str:
    if value in (None, "", []):
        return "—"
    if isinstance(value, list):
        return ", ".join(json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v) for v in value)
    return str(value).replace("|", "/").replace("\n", " ")


def write_scores(path: Path, label: str, provider: str, model: str, detail: str | None, rows: list[dict]) -> None:
    cost = total_cost(rows)
    roles_right = sum(r["roles"]["matched"] for r in rows)
    roles_total = sum(len(r["roles"]["saved"]) for r in rows)
    out = [
        f"# Tagging eval: {label}",
        "",
        f"`{model}` ({provider}){f', image detail {detail}' if detail else ''}, {len(rows)} calls"
        + (f", estimated cost ${cost:.4f}." if cost is not None else "."),
        "Each field is compared with the saved record, which the owner reviewed. Records first tagged by one",
        "provider and kept as they were favor that provider, so read the differences, not only the rates.",
        "",
        "| Field | Matched | Compared | Rate |",
        "|---|---|---|---|",
    ]
    for field, matched, compared in field_rates(rows):
        rate = f"{matched / compared:.0%}" if compared else "—"
        out.append(f"| {field} | {matched} | {compared} | {rate} |")
    if roles_total:
        out.append(f"| photo roles | {roles_right} | {roles_total} | {roles_right / roles_total:.0%} |")
    out += ["", "## Each garment", ""]
    for r in rows:
        out.append(f"### #{r['garment_id']} {r['name']}, run {r['run']}")
        if r["error"]:
            out += [f"Failed: {r['error']}", ""]
            continue
        differ = [f for f, outcome in r["fields"].items() if outcome == DIFFER and not f.endswith("±1")]
        out.append("Differences: " + ("none" if not differ else ""))
        for field in differ:
            out.append(f"- {field}: saved {_shown(r['saved'][field])} · tagged {_shown(r['tagged'][field])}")
        if r["roles"]["matched"] != len(r["roles"]["saved"]):
            out.append(f"- photo roles: saved {', '.join(r['roles']['saved'])} · tagged {', '.join(r['roles']['tagged'])}")
        for field in SHOWN_FIELDS:
            out.append(f"- {field}: saved {_shown(r['saved'][field])} · tagged {_shown(r['tagged'][field])}")
        out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def run(label: str, runs: int, user_id: int, db_path: Path, ids: list[int] | None, limit: int, is_test: bool,
        out_root: Path, detail: str | None = None) -> Path:
    user = db.select_user(db_path, user_id)
    if user is None:
        raise ValueError(f"No user {user_id} in {db_path}")
    chosen = choose_garments(db.select_owned_garments(db_path, user_id), ids, limit)
    if not chosen:
        raise ValueError(f"User {user_id} has no garments with photos")
    saved_prefs = db.select_preferences(db_path, user_id)
    preferences = saved_prefs[0] if saved_prefs else None
    provider = active_provider()
    model = model_for(provider, "tag")

    out_dir = out_root / f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{label}"
    out_dir.mkdir(parents=True)
    client = None if is_test else make_client()
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as scratch:
        log_path = Path(scratch) / "tagging_log.jsonl"   # a failed call's tokens are logged here, not in the app's log
        for number, garment in enumerate(chosen, start=1):
            paths = photos.get_photo_paths(garment.id)
            for repeat in range(1, runs + 1):
                print(f"[{number}/{len(chosen)}] #{garment.id} {garment.name} run {repeat}/{runs}…", file=sys.stderr, flush=True)
                row = {"garment_id": garment.id, "name": garment.name, "run": repeat, "label": label,
                       "provider": provider, "model": model, "image_detail": detail, "usage": None, "error": None,
                       "saved": garment.model_dump(mode="json"), "tagged": None, "fields": {},
                       "roles": {"saved": saved_roles(paths), "tagged": [], "matched": 0}}
                try:
                    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
                        sendable = photos.sendable_copies(paths, Path(tmp))
                        result, usage = tag_photos(user_id, sendable, log_path, client, is_test, None, user.language, preferences)
                except (ServiceError, UnusableResponse, OSError, ValueError) as error:   # one bad garment shouldn't stop the run
                    row["error"] = f"{getattr(error, 'kind', type(error).__name__)}: {error}"
                    if isinstance(error, UnusableResponse):   # it answered, so its tokens count toward the cost
                        row["usage"] = error.usage.model_dump()
                else:
                    row["usage"] = usage.model_dump() if usage else None
                    row["tagged"] = result.garment.model_dump(mode="json")
                    row["fields"] = compare(garment, result.garment)
                    tagged_roles = {tag.index: tag.role for tag in result.photos}
                    row["roles"]["tagged"] = [tagged_roles.get(i, "—") for i in range(len(paths))]
                    row["roles"]["matched"] = role_matches(row["roles"]["saved"], result)
                rows.append(row)
                with (out_dir / "results.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_scores(out_dir / "scores.md", label, provider, model, detail, rows)
    cost = total_cost(rows)
    failed = sum(1 for r in rows if r["error"])
    print(f"\n{len(rows)} calls, {failed} failed" + (f", about ${cost:.4f}." if cost is not None else "."))
    print(f"Read it: {out_dir / 'scores.md'}")
    return out_dir


def main() -> None:
    load_dotenv()   # first: it can set the provider
    parser = argparse.ArgumentParser(prog="eval-tags", description="Re-tag saved garments and compare with their records.")
    parser.add_argument("-l", "--label", required=True, help="Name for this run, e.g. terra-tags (used in the folder name)")
    parser.add_argument("--ids", type=int, nargs="+", metavar="ID", help="Re-tag these garments only")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"How many garments, spread across categories (default {DEFAULT_LIMIT})")
    parser.add_argument("--runs", type=int, default=1, help="How many times to tag each garment (default 1)")
    parser.add_argument("--user", type=int, default=config.DEFAULT_USER_ID, help="Whose wardrobe (default: the owner)")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="Database to read (default: the app's). Nothing is written to it")
    parser.add_argument("-p", "--provider", choices=list(config.MODELS_BY_PROVIDER),
                        help=f"Run on this provider instead of the configured one ({PROVIDER_VARIABLE} or config.LLM_PROVIDER)")
    parser.add_argument("-m", "--model", help="Tag on this model instead of the provider's configured one. It has to be one of that provider's models")
    parser.add_argument("--image-detail", choices=["low", "high", "original", "auto"],
                        help=f"OpenAI only: the photos' detail level instead of {config.OPENAI_IMAGE_DETAIL}")
    parser.add_argument("-t", "--test", action="store_true", help="Use the canned test tags: checks the script, spends no tokens")
    args = parser.parse_args()
    if args.runs < 1 or args.limit < 1:
        parser.error("--runs and --limit must be at least 1")
    if not all(c.isalnum() or c in "-_." for c in args.label):
        parser.error("--label may only use letters, digits, - _ and .")
    if args.provider:
        os.environ[PROVIDER_VARIABLE] = args.provider   # this run only: llm reads it at each call
    if args.model:
        config.MODELS_BY_PROVIDER[active_provider()]["tag"] = args.model   # this run only, likewise
    if args.image_detail:
        if active_provider() != "openai":
            parser.error("--image-detail only applies to the openai provider")
        config.OPENAI_IMAGE_DETAIL = args.image_detail   # this run only: llm reads it at each call
    try:
        run(args.label, args.runs, args.user, args.db, args.ids, args.limit, args.test, TAG_EVALS_DIR, args.image_detail)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
