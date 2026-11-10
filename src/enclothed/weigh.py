"""weigh (#2): should I buy this? A garment photographed while shopping, judged against the wardrobe.

The flow, after the photos are tagged into a draft and reviewed (drafts.py):
1. Shortlist the owned garments most like the candidate, in code (similar_garments).
2. One LLM call returns the verdict and outfits built around the candidate (llm.weigh_candidate).
3. Only then is the draft saved, as a candidate (weighed_on set), with its verdict and outfits.

The candidate has no garment ID during the call, so it goes in as CANDIDATE_ID (0, which no real
garment has) and is swapped for its real ID once the call has succeeded. If the call fails, the
draft is untouched and the owner can try again without paying to tag the photos twice.
"""
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from anthropic import Anthropic

from enclothed import config, db, drafts
from enclothed.llm import WEIGH_INSTRUCTIONS, UnusableResponse, weigh_candidate
from enclothed.models import DEFAULT_LANGUAGE, Garment, Language, Outfit, OutfitResult, TokenUsage, WeighOut, WeighResult
from enclothed.outfit import options_text, tier_plan, validate_outfits, wardrobe_block, wardrobe_for_prompt
from enclothed.similarity import similar_garments
from enclothed.usage import log_failed_call

logger = logging.getLogger(__name__)

CANDIDATE_ID = 0   # SQLite row IDs start at 1, so 0 can never be a real garment


class DraftGone(LookupError):
    """The draft to weigh no longer exists: already weighed or added, discarded, or expired."""


def weigh_context(owned: dict[int, Garment], candidate: Garment, similar: list[int], preferences: str | None,
                  plan: dict, caching: bool = True) -> list[dict]:
    """The message: the cached wardrobe first, then everything about this candidate."""
    candidate_record = wardrobe_for_prompt({CANDIDATE_ID: candidate})
    context = [wardrobe_block(wardrobe_for_prompt(owned), caching)]
    if preferences:
        context.append({"type": "text", "text": f"<preferences>\n{preferences}\n</preferences>"})
    context += [
        {"type": "text", "text": f"<candidate>\n{json.dumps(candidate_record, ensure_ascii=False)}\n</candidate>"},
        {"type": "text", "text": "<similar>\n" + ("\n".join(f"{i}: {owned[i].name}" for i in similar) or "(nothing owned in this category)") + "\n</similar>"},
        {"type": "text", "text": f"<anchors>\n{CANDIDATE_ID}: {candidate.name}\n</anchors>"},
        {"type": "text", "text": options_text(plan)},
        {"type": "text", "text": WEIGH_INSTRUCTIONS},
    ]
    return context


def check_similar(result: WeighResult, similar: list[int]) -> tuple[list[str], WeighResult]:
    """Keep only matches the model was asked about, so the verdict never points at a garment it wasn't shown."""
    kept = [m for m in result.similar if m.garment_id in similar]
    dropped = sorted({m.garment_id for m in result.similar} - set(similar))
    problems = [f"similar: dropped garment id(s) not in <similar>: {dropped}"] if dropped else []
    return problems, result.model_copy(update={"similar": kept})


def with_real_id(outfit: Outfit, garment_id: int) -> Outfit:
    """The outfit with the placeholder candidate ID swapped for the saved garment's ID."""
    garments = [g.model_copy(update={"garment_id": garment_id}) if g.garment_id == CANDIDATE_ID else g for g in outfit.garments]
    return outfit.model_copy(update={"garments": garments})


def log_weigh(log_path: Path, user_id: int, garment_id: int, result: WeighResult, usage: TokenUsage, context: list[dict],
              problems: list[str], timestamp: str) -> None:
    entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "garment_id": garment_id,
        "usage": usage.model_dump(),
        "result": result.model_dump(mode="json"),
        "context": "\n".join(block["text"] for block in context),
        "problems": problems,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def weigh_draft(db_path: Path, drafts_dir: Path, garments_dir: Path, tagging_log: Path, weigh_log: Path, user_id: int,
                draft_id: str, garment: Garment, client: Anthropic, preferences: str | None = None,
                language: Language = DEFAULT_LANGUAGE, caching: bool = True) -> tuple[WeighOut, int, list[int]]:
    """Weigh a reviewed draft. Returns the saved verdict, the candidate's new garment ID, and the new outfit IDs."""
    if not drafts.has_draft(drafts_dir, user_id, draft_id):   # before paying for the call
        raise DraftGone(draft_id)

    owned = {g.id: g for g in db.select_owned_garments(db_path, user_id)}
    candidate = garment.model_copy(update={"id": CANDIDATE_ID})
    similar = similar_garments(candidate, owned)
    plan = tier_plan(config.WEIGH_OUTFIT_COUNT, None)
    context = weigh_context(owned, candidate, similar, preferences, plan, caching)

    try:
        result, usage = weigh_candidate(client, context, language)
    except UnusableResponse as error:
        log_failed_call(weigh_log, user_id, error.usage, str(error))
        raise

    problems, result = check_similar(result, similar)
    outfit_problems, valid_outfits = validate_outfits(OutfitResult(outfits=result.outfits), {**owned, CANDIDATE_ID: candidate}, [CANDIDATE_ID], plan)
    problems += outfit_problems
    for problem in problems:
        logger.warning("Weigh validation: %s", problem)

    garment_id = drafts.confirm_draft(drafts_dir, db_path, garments_dir, tagging_log, user_id, draft_id, garment, weighed_on=date.today())
    if garment_id is None:   # discarded in another tab while the call ran: nothing to attach the verdict to
        raise DraftGone(draft_id)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    outfits = [with_real_id(o, garment_id) for o in valid_outfits]
    outfit_ids = db.insert_outfits(db_path, user_id, outfits, [garment_id], f"Weighing: {garment.name}", timestamp)
    verdict = result.verdict()
    db.insert_weigh(db_path, user_id, garment_id, verdict, timestamp)
    log_weigh(weigh_log, user_id, garment_id, result, usage, context, problems, timestamp)
    return WeighOut(garment_id=garment_id, weighed_at=timestamp, verdict=verdict), garment_id, outfit_ids
