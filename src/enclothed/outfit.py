from anthropic import Anthropic
from enclothed.models import DEFAULT_LANGUAGE, Garment, Language, TokenUsage, Outfit, OutfitDescription, OutfitResult, Category, RiskTier, Silhouette, layer_for
from enclothed.llm import UnusableResponse, describe_outfit, recommend_outfits
from enclothed.usage import log_failed_call
from enclothed import config
from enclothed.db import insert_outfits
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import get_args

logger = logging.getLogger(__name__)

OUTFIT_INCLUDE_FIELDS = {
    "category","subcategory",
    "primary_color","secondary_colors","accent_colors",
    "materials","warmth","pattern",
    "brand",
    "style_tags",
    "styling_notes",
    "fit","sheen","formality",
    "fabric_type","shape","hem","fabric_weight","sleeve","statement",
    "set_id",
}

TEST_OUTFITS = OutfitResult.model_validate({
    "outfits": [
        {
            "aesthetic": "Japanese resort casual",
            "garments": [
                {"garment_id": 6, "styling_advice": "Button it up and let it hang loose and untucked"},
                {"garment_id": 15, "styling_advice": "Leave the cropped hem bare to show the shoes"},
                {"garment_id": 27, "styling_advice": "Wear with no-show socks to keep it light"},
            ],
            "explanation": (
                "The drapey printed camp shirt is the one focal point, so the rest stays quiet. "
                "Washed indigo pants and slate-blue sneakers pick up the cool tones in the faded charcoal ground. "
                "Everything is breathable and loose, which suits 21°C sun and a relaxed lunch."
            ),
            "missing": None,
            "risk_tier": "safe",
        },
        {
            "aesthetic": "Relaxed earth tones",
            "garments": [
                {"garment_id": 10, "styling_advice": "Wear untucked with the sleeves pushed up"},
                {"garment_id": 73, "styling_advice": "Cuff the hem once for a clean ankle line"},
                {"garment_id": 23, "styling_advice": "Keep the laces neat for a polished casual finish"},
            ],
            "explanation": (
                "Rust linen, khaki chinos and camel leather sneakers make a warm, tonal palette. "
                "The slubby linen against the smooth twill adds texture. "
                "The look is easy and casual, with the slightly cropped chino showing off the sneakers."
            ),
            "missing": None,
            "risk_tier": "stretch",
        },
        {
            "aesthetic": "Dark minimalist",
            "garments": [
                {"garment_id": 52, "styling_advice": "Let the sleeves bunch slightly at the wrists"},
                {"garment_id": 77, "styling_advice": "Cinch the drawstring and keep the fit easy"},
                {"garment_id": 25, "styling_advice": "Go sockless for an effortless summery feel"},
                {"garment_id": 51, "styling_advice": "Wear open so the hem drapes behind you"},
            ],
            "explanation": (
                "A black long-sleeve tee and tapered pinstripe pants keep the lower half slim under the oversized, draped open jacket. "
                "The palette stays monochrome, with texture from the slubby linen and woven leather mules. "
                "The jacket is light enough for 21°C and easy to take off in the sun."
            ),
            "missing": None,
            "risk_tier": "bold",
        },
    ]
})


def get_outfits(db_path: Path, user_id: int, wardrobe: dict[int, Garment], anchors: list[int] | None, logging_path: Path, client: Anthropic | None, prompt_message: str, is_test: bool, caching: bool = True, formality: int = 1, warmth: int = 1, preferences: str | None = None, language: Language = DEFAULT_LANGUAGE, count: int = config.DEFAULT_OUTFIT_COUNT, riskiness: RiskTier | None = None, silhouette: Silhouette | None = None) -> OutfitResult:
    result, _ = generate_outfits(db_path, user_id, wardrobe, anchors, logging_path, client, prompt_message, is_test, caching, preferences, language, count, riskiness, silhouette)
    return result

def generate_outfits(db_path: Path, user_id: int, wardrobe: dict[int, Garment], anchors: list[int] | None, logging_path: Path, client: Anthropic | None, prompt_message: str, is_test: bool, caching: bool = True, preferences: str | None = None, language: Language = DEFAULT_LANGUAGE, count: int = config.DEFAULT_OUTFIT_COUNT, riskiness: RiskTier | None = None, silhouette: Silhouette | None = None) -> tuple[OutfitResult, list[int]]:
    """Ask the LLM for outfits, save the valid ones, and return the result plus the new outfit ids."""
    # TODO: filters (ADR-039 O8)
    prompt_wardrobe = wardrobe_for_prompt(wardrobe)

    logger.debug(json.dumps(prompt_wardrobe, ensure_ascii=False, indent=2))

    context = [wardrobe_block(prompt_wardrobe, caching)]

    if preferences:
        context.append({"type": "text", "text": f"<preferences>\n{preferences}\n</preferences>"})

    if anchors:
        anchors_text = "\n<anchors>\n"
        anchors_text += "\n".join(f"{i}: {wardrobe[i].name}" for i in anchors)
        anchors_text += "\n</anchors>"
        anchors_block = {
            "type": "text",
            "text": anchors_text,
        }
        context.append(anchors_block)
    if prompt_message:
        request_block = {
            "type": "text",
            "text": f"<request>{prompt_message}</request>"
        }
        context.append(request_block)

    plan = tier_plan(count, riskiness)
    context.append({"type": "text", "text": options_text(plan, silhouette)})

    try:
        wrapper, usage = (TEST_OUTFITS, None) if is_test else recommend_outfits(client, context, language)
    except UnusableResponse as error:
        log_failed_call(logging_path, user_id, error.usage, str(error))
        raise

    wrapper = fill_single_tier(wrapper, plan)
    problems, valid_outfits = validate_outfits(wrapper, wardrobe, anchors, plan)
    for problem in problems:
        logger.warning("Validation: %s", problem)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    new_ids: list[int] = []
    if not is_test:
        if len(valid_outfits) < len(wrapper.outfits):
            logger.warning("Saving %d of %d outfits", len(valid_outfits), len(wrapper.outfits))
        new_ids = insert_outfits(db_path, user_id, valid_outfits, anchors, prompt_message, timestamp)

    log_outfit(logging_path, user_id, anchors, wrapper, usage, "\n".join(block["text"] for block in context), problems, timestamp)

    return wrapper, new_ids

def tier_plan(count: int, riskiness: RiskTier | None) -> dict[RiskTier, int]:
    """How many outfits to ask for at each tier.

    With a riskiness, every outfit is at that tier. Without one, the count is spread across
    safe, stretch and bold, with any remainder going to safe first, then stretch:
    1 -> 1/0/0, 2 -> 1/1/0, 3 -> 1/1/1, 4 -> 2/1/1, 5 -> 2/2/1.
    """
    if not config.MIN_OUTFIT_COUNT <= count <= config.MAX_OUTFIT_COUNT:
        raise ValueError(f"count must be {config.MIN_OUTFIT_COUNT}-{config.MAX_OUTFIT_COUNT}; got {count}")
    tiers: tuple[RiskTier, ...] = get_args(RiskTier)
    if riskiness is not None:
        return {tier: (count if tier == riskiness else 0) for tier in tiers}
    base, extra = divmod(count, len(tiers))
    return {tier: base + (1 if i < extra else 0) for i, tier in enumerate(tiers)}

def options_text(plan: dict[RiskTier, int], silhouette: Silhouette | None = None) -> str:
    total = sum(plan.values())
    wanted = ", ".join(f"{n} {tier}" for tier, n in plan.items() if n)
    article = "a" if silhouette == "Y" else "an"   # "a Y-line" (why), but "an A-, H-, I-, O-, X-line"
    shape = f"\nEvery outfit forms {article} {silhouette}-line silhouette." if silhouette else ""
    return f"<options>\nSuggest exactly {total} outfit{'s' if total != 1 else ''}: {wanted}.{shape}\n</options>"

def fill_single_tier(result: OutfitResult, plan: dict[RiskTier, int]) -> OutfitResult:
    """When every outfit was asked for at one tier, fill in any tier the LLM left blank."""
    asked = [tier for tier, n in plan.items() if n]
    if len(asked) != 1 or all(o.risk_tier for o in result.outfits):
        return result
    return result.model_copy(update={"outfits": [
        o if o.risk_tier else o.model_copy(update={"risk_tier": asked[0]}) for o in result.outfits
    ]})

def wardrobe_block(prompt_wardrobe: dict, caching: bool) -> dict:
    """The <wardrobe> block. It's the largest and steadiest part of the message, so it goes first and
    is marked for caching: the next call with the same wardrobe reads it from the cache."""
    block = {"type": "text", "text": f"<wardrobe>\n{json.dumps(prompt_wardrobe, ensure_ascii=False)}\n</wardrobe>\n"}
    if caching:
        block["cache_control"] = {"type": "ephemeral"}
    return block

def wardrobe_for_prompt(wardrobe: dict[int, Garment]) -> dict:
    records = {}
    for key, garment in wardrobe.items():
        record = garment.model_dump(mode="json", include=OUTFIT_INCLUDE_FIELDS, exclude_none=True)
        layer = layer_for(garment.category, garment.subcategory)
        if layer:
            record["layer"] = layer
        records[key] = record
    return records

def log_outfit(log_path: Path, user_id: int, anchors: list[int] | None, result: OutfitResult, usage: TokenUsage | None, context: str, problems: list[str], timestamp: str) -> None:
    entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "anchors": anchors,
        "usage": usage.model_dump() if usage else None,
        "result": result.model_dump(mode="json"),
        "context": context,
        "problems": problems,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def fill_description(log_path: Path, user_id: int, pieces: dict[int, Garment], client: Anthropic, details: str | None,
                     aesthetic: str | None, explanation: str | None, preferences: str | None = None,
                     language: Language = DEFAULT_LANGUAGE) -> OutfitDescription:
    """Ask the LLM for whichever of the name and explanation are blank. What the user wrote is kept as is.

    Callers skip this when both are written, so it always spends tokens. Logs to the outfit log, so the
    usage page counts it under outfits.
    """
    context = [{"type": "text", "text": f"<outfit>\n{json.dumps(wardrobe_for_prompt(pieces), ensure_ascii=False)}\n</outfit>"}]
    if details:
        context.append({"type": "text", "text": f"<occasion>\n{details}\n</occasion>"})
    if preferences:
        context.append({"type": "text", "text": f"<preferences>\n{preferences}\n</preferences>"})
    given = {key: value for key, value in (("aesthetic", aesthetic), ("explanation", explanation)) if value}
    if given:
        context.append({"type": "text", "text": f"<given>\n{json.dumps(given, ensure_ascii=False)}\n</given>"})

    try:
        answer, usage = describe_outfit(client, context, language)
    except UnusableResponse as error:
        log_failed_call(log_path, user_id, error.usage, str(error))
        raise
    # The LLM is told to return given text unchanged; code makes sure of it.
    filled = OutfitDescription(aesthetic=aesthetic or answer.aesthetic.strip(), explanation=explanation or answer.explanation.strip())
    if not filled.aesthetic or not filled.explanation:
        log_failed_call(log_path, user_id, usage, "Blank name or explanation in description")
        raise UnusableResponse("Blank name or explanation in description", usage)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "kind": "describe",
        "garment_ids": list(pieces),
        "usage": usage.model_dump(),
        "given": given,
        "result": filled.model_dump(),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return filled

def validate_outfits(result: OutfitResult, wardrobe: dict[int, Garment], anchors: list[int] | None, plan: dict[RiskTier, int] | None = None) -> tuple[list[str], list[Outfit]]:
    """Check the reply against what was asked for. A wrong count or tier mix is reported but drops nothing."""
    problems: list[str] = []
    valid: list[Outfit] = []

    if plan is not None:
        expected = sum(plan.values())
        count = len(result.outfits)
        if count != expected:
            problems.append(f"{count} outfit(s) returned, expected {expected}")
        else:   # a wrong count always gives a wrong mix too, so only check the mix when the count is right
            returned = Counter(o.risk_tier or "untiered" for o in result.outfits)
            wanted = {tier: n for tier, n in plan.items() if n}
            if dict(returned) != wanted:
                problems.append(f"tiers returned {dict(sorted(returned.items()))}, expected {dict(sorted(wanted.items()))}")

    for number, outfit in enumerate(result.outfits, start=1):
        outfit_problems = validate_outfit(outfit, wardrobe, anchors)
        for problem in outfit_problems:
            problems.append(f"Outfit {number}: {problem}")
        if not outfit_problems:
            valid.append(outfit)

    return problems, valid

def validate_outfit(outfit: Outfit, wardrobe: dict[int, Garment], anchors: list[int] | None) -> list[str]:
    problems = []
    outfit_ids = {g.garment_id for g in outfit.garments}
    missing = set(anchors or []) - outfit_ids
    if missing:
        problems.append(f"anchor(s) {sorted(missing)} missing")

    if len(outfit_ids) < len(outfit.garments):
        problems.append("duplicate garments found in outfit")

    unknown = outfit_ids - wardrobe.keys()

    if unknown:
        problems.append(f"unknown garment id(s) {sorted(unknown)}")
    category_counts = count_categories(outfit_ids - unknown, wardrobe)

    if not ((category_counts["top"] and category_counts["bottom"]) or category_counts["one-piece"]):
        problems.append("body is not covered by a top and a bottom or a one-piece")

    if not category_counts["shoes"]:
        problems.append("outfit has no footwear suggestion")

    if category_counts["shoes"] > 1:
        problems.append("outfit suggests multiple shoes")

    return problems

def count_categories(garment_ids: set[int], wardrobe: dict[int, Garment]) -> dict[str, int]:
    counter = dict.fromkeys(get_args(Category), 0)
    for garment_id in garment_ids:
        counter[wardrobe[garment_id].category] += 1
    return counter
