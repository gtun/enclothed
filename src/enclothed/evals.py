"""eval-outfits: rerun a fixed set of outfit requests so prompt versions can be compared fairly.

Each run works on a copy of the database, so nothing it suggests lands in the real outfits list
or skews the likes. It writes one folder per run under data/evals/:

    prompt.txt     the exact system prompt used, so you can tell versions apart later
    results.jsonl  one line per request and repeat: the outfits, validation problems, tokens
    scores.md      a table to fill in by hand, plus each outfit's pieces and explanation

Usage:
    uv run eval-outfits --label v1-placeholder            # every request, twice
    uv run eval-outfits --label v2-rule-of-one --runs 3 --only dinner-rain office
    uv run eval-outfits --label smoke --test              # canned outfits, no tokens
    uv run eval-outfits --label opus-trial --model claude-opus-5-5   # the same requests on another model
    uv run eval-outfits --label terra-trial --provider openai        # the same requests on another provider

On the server: docker exec enclothed /app/.venv/bin/eval-outfits --label ...
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from enclothed import config, db
from enclothed.llm import PROVIDER_VARIABLE, active_provider, make_client, model_for, outfit_system_prompt
from enclothed.models import Garment, RiskTier, TokenUsage
from enclothed.outfit import generate_outfits, tier_plan
from enclothed.usage import call_cost

REQUESTS_PATH = config.PKG_DIR / "eval_requests.json"
EVALS_DIR = config.DATA_DIR / "evals"

# The rubric columns in scores.md. Weather is pass/fail: any fail is a bug, not a matter of taste.
RUBRIC = ["Weather OK (y/n)", "Right tier (y/n)", "Rule + anchor named (y/n)", "Would wear (1-3)", "Notes"]


def load_requests(path: Path, only: list[str] | None) -> list[dict]:
    requests = json.loads(path.read_text(encoding="utf-8"))["requests"]
    ids = [r["id"] for r in requests]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: request ids must be unique")
    if only:
        unknown = set(only) - set(ids)
        if unknown:
            raise ValueError(f"No request with id {sorted(unknown)}. Known: {ids}")
        requests = [r for r in requests if r["id"] in only]
    for r in requests:
        tier_plan(r.get("count", config.DEFAULT_OUTFIT_COUNT), r.get("riskiness"))   # fail before spending tokens
    return requests


def copy_db(source: Path, target: Path) -> None:
    """A consistent copy even if the app is writing at the same time."""
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def piece_lines(outfit: dict, wardrobe: dict[int, Garment]) -> list[str]:
    lines = []
    for g in outfit["garments"]:
        garment = wardrobe.get(g["garment_id"])
        name = garment.name if garment else "(not in wardrobe)"
        advice = f" — {g['styling_advice']}" if g.get("styling_advice") else ""
        lines.append(f"  - #{g['garment_id']} {name}{advice}")
    return lines


def total_cost(rows: list[dict]) -> float | None:
    """Estimated dollars for the run's calls, or None when none of them has a price (test mode, an unpriced model)."""
    costs = [call_cost(TokenUsage.model_validate(row["usage"])) for row in rows if row["usage"]]
    priced = [cost for cost in costs if cost is not None]
    return sum(priced) if priced else None


def write_scores(path: Path, label: str, prompt_hash: str, provider: str, model: str, rows: list[dict],
                 wardrobe: dict[int, Garment]) -> None:
    cell = lambda text: str(text).replace("|", "/").replace("\n", " ")
    cost = total_cost(rows)
    out = [
        f"# Outfit eval: {label}",
        "",
        f"Prompt `{prompt_hash}` on `{model}` ({provider}). Fill in the columns, then compare with the last run's scores.md.",
        *([f"Estimated cost: ${cost:.4f} for {len(rows)} calls."] if cost is not None else []),
        "Mark a tier wrong when a 'bold' outfit is really safe, or a 'safe' one is risky.",
        "",
        "| Request | Run | # | Tier | Outfit | " + " | ".join(RUBRIC) + " |",
        "|" + "---|" * (5 + len(RUBRIC)),
    ]
    for row in rows:
        for n, outfit in enumerate(row["outfits"], start=1):
            out.append(f"| {row['request_id']} | {row['run']} | {n} | {outfit.get('risk_tier') or '?'} | "
                       f"{cell(outfit['aesthetic'])} |" + " |" * len(RUBRIC))
    out += ["", "## The outfits", ""]
    for row in rows:
        out.append(f"### {row['request_id']}, run {row['run']}")
        out.append(f"Asked: {row['details']} · {row['options']}")
        if row["problems"]:
            out.append("Validation: " + "; ".join(row["problems"]))
        out.append("")
        for n, outfit in enumerate(row["outfits"], start=1):
            out.append(f"**{n}. {outfit['aesthetic']}** ({outfit.get('risk_tier') or 'no tier'})")
            out += piece_lines(outfit, wardrobe)
            out.append(f"  {outfit['explanation']}")
            if outfit.get("missing"):
                out.append(f"  Missing: {outfit['missing']}")
            out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def run(label: str, runs: int, user_id: int, db_path: Path, requests_path: Path, only: list[str] | None,
        is_test: bool, out_root: Path) -> Path:
    requests = load_requests(requests_path, only)
    user = db.select_user(db_path, user_id)
    if user is None:
        raise ValueError(f"No user {user_id} in {db_path}")
    saved = db.select_preferences(db_path, user_id)
    preferences = saved[0] if saved else None
    prompt = outfit_system_prompt(user.language)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = out_root / f"{stamp}_{label}"
    out_dir.mkdir(parents=True)
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    provider = active_provider()
    model = model_for(provider, "outfits")
    client = None if is_test else make_client()
    rows: list[dict] = []
    totals = {"input": 0, "output": 0, "cache_read": 0}
    with tempfile.TemporaryDirectory() as scratch:
        work_db = Path(scratch) / "eval.db"
        log_path = Path(scratch) / "outfit_log.jsonl"
        copy_db(db_path, work_db)
        wardrobe = {g.id: g for g in db.select_owned_garments(work_db, user_id)}
        if not wardrobe:
            raise ValueError(f"User {user_id} has no garments to suggest from")

        for request in requests:
            count = request.get("count", config.DEFAULT_OUTFIT_COUNT)
            riskiness: RiskTier | None = request.get("riskiness")
            anchors = request.get("anchors") or None
            silhouette = request.get("silhouette")
            plan = tier_plan(count, riskiness)
            options = ", ".join(f"{n} {tier}" for tier, n in plan.items() if n) + (f", {silhouette}-line" if silhouette else "")
            for repeat in range(1, runs + 1):
                print(f"{request['id']} run {repeat}/{runs}…", file=sys.stderr, flush=True)
                result, _ = generate_outfits(work_db, user_id, wardrobe, anchors, log_path, client, request["details"],
                                             is_test, True, preferences, user.language, count, riskiness, silhouette)
                entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
                usage = entry["usage"] or {}
                totals["input"] += usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
                totals["output"] += usage.get("output_tokens", 0)
                row = {
                    "request_id": request["id"], "run": repeat, "details": request["details"], "options": options,
                    "anchors": anchors, "prompt_hash": prompt_hash, "label": label, "provider": provider, "model": model,
                    "outfits": result.model_dump(mode="json")["outfits"],
                    "problems": entry["problems"], "usage": entry["usage"],
                }
                rows.append(row)
                with (out_dir / "results.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_scores(out_dir / "scores.md", label, prompt_hash, provider, model, rows, wardrobe)
    problem_count = sum(len(r["problems"]) for r in rows)
    print(f"\n{len(rows)} calls, {sum(len(r['outfits']) for r in rows)} outfits, {problem_count} validation problem(s).")
    cost = total_cost(rows)
    print(f"Tokens: {totals['input']:,} in, {totals['cache_read']:,} cached reads, {totals['output']:,} out"
          + (f", about ${cost:.4f}." if cost is not None else "."))
    print(f"Score it: {out_dir / 'scores.md'}")
    return out_dir


def main() -> None:
    load_dotenv()   # first: it can set the provider
    parser = argparse.ArgumentParser(prog="eval-outfits", description="Rerun the fixed outfit requests to compare prompt versions.")
    parser.add_argument("-l", "--label", required=True, help="Name for this prompt version, e.g. v2-rule-of-one (used in the folder name)")
    parser.add_argument("--runs", type=int, default=2, help="How many times to run each request (default 2; output varies between runs)")
    parser.add_argument("--user", type=int, default=config.DEFAULT_USER_ID, help="Whose wardrobe and style notes to use (default: the owner)")
    parser.add_argument("--only", nargs="+", metavar="ID", help="Run only these request ids")
    parser.add_argument("--requests", type=Path, default=REQUESTS_PATH, help="A different requests file")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="Database to copy from (default: the app's)")
    parser.add_argument("-p", "--provider", choices=list(config.MODELS_BY_PROVIDER),
                        help=f"Run on this provider instead of the configured one ({PROVIDER_VARIABLE} or config.LLM_PROVIDER)")
    parser.add_argument("-m", "--model", help="Run the outfit calls on this model instead of the provider's configured one, e.g. claude-opus-5-5 to compare. It has to be one of that provider's models")
    parser.add_argument("-t", "--test", action="store_true", help="Use the canned test outfits: checks the script, spends no tokens")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if not all(c.isalnum() or c in "-_." for c in args.label):
        parser.error("--label may only use letters, digits, - _ and .")
    if args.provider:
        os.environ[PROVIDER_VARIABLE] = args.provider   # this run only: llm reads it at each call
    if args.model:
        config.MODELS_BY_PROVIDER[active_provider()]["outfits"] = args.model   # this run only, likewise
    try:
        run(args.label, args.runs, args.user, args.db, args.requests, args.only, args.test, EVALS_DIR)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
