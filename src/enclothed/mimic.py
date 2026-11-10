"""mimic (#5): recreate a photographed look from garments the user already owns.

1. create_look: one vision call breaks the photos down into the look's pieces, tagged with the wardrobe's own
   fields (llm.tag_look). The look and its photos are saved right away, because those tokens are spent.
2. recreate: for each piece, the owned garments most like it on paper are shortlisted in code (similarity.py).
   Then one text-only call, on the cached wardrobe, returns up to two recreations: a stand-in and a closeness
   for every piece (llm.match_look). The reply is checked, and the valid recreations are saved as outfits
   (source 'ai', look_id set) with their matches.

The photos are seen once, in step 1. If step 2 fails, the look is kept, and matching it again costs only the
text call (the API's "match again").
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic

from enclothed import config, db, photos
from enclothed.llm import MIMIC_INSTRUCTIONS, UnusableResponse, match_look, tag_look
from enclothed.models import (
    DEFAULT_LANGUAGE, Garment, Language, LookMatchOut, LookPiece, LookTags, MimicOutfit, MimicResult, Outfit,
    OutfitGarment, TokenUsage, layer_for,
)
from enclothed.outfit import validate_outfit, wardrobe_block, wardrobe_for_prompt
from enclothed.similarity import similar_garments
from enclothed.usage import log_failed_call

logger = logging.getLogger(__name__)

REQUEST_PREFIX = "Mimicking: "   # the saved outfits' request, so the outfits page groups each look's recreations

# What -t uses instead of the two calls: a plain look any wardrobe can try to match.
TEST_LOOK = LookTags(
    title="Navy and white casual",
    summary="A relaxed navy overshirt worn open over a white tee, straight light-wash jeans and white sneakers. "
            "Tonal blues with white, an easy H-line.",
    silhouette="H",
    pieces=[
        LookPiece(category="outerwear", subcategory="shirt jacket", primary_color="navy", fit="relaxed", shape="boxy",
                  hem="hip", description="A boxy navy overshirt worn open.", role="the structure on top"),
        LookPiece(category="top", subcategory="t-shirt", primary_color="white", fit="regular",
                  description="A plain white crewneck tee.", role="the bright base layer"),
        LookPiece(category="bottom", subcategory="jeans", primary_color="light blue", shape="straight", hem="ankle",
                  description="Straight light-wash jeans, cuffed once.", role="the relaxed straight line below"),
        LookPiece(category="shoes", subcategory="low-top sneakers", primary_color="white",
                  description="Clean white low-top sneakers.", role="echoes the white tee", essential=False),
    ],
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(log_path: Path, entry: dict) -> None:
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- step 1: the look --------------------------------------------------------------------------
def create_look(db_path: Path, user_id: int, photo_paths: list[Path], note: str | None, client: Anthropic | None,
                language: Language, log_path: Path, is_test: bool = False) -> tuple[int | None, LookTags]:
    """Tag the look's photos and save the look, with its photos moved into its folder.
    Returns the new look's ID (None in test mode, which saves nothing) and its tags."""
    if is_test:
        return None, TEST_LOOK
    try:
        tags, usage = tag_look(client, photo_paths, note, language)
    except UnusableResponse as error:
        log_failed_call(log_path, user_id, error.usage, str(error))
        raise

    created_at = _now()
    look_id = db.insert_look(db_path, user_id, tags, note, created_at)
    photos.save_look_photos(look_id, photo_paths)
    _log(log_path, {"timestamp": created_at, "user_id": user_id, "kind": "tag-look", "look_id": look_id,
                    "usage": usage.model_dump(), "result": tags.model_dump(mode="json"), "note": note})
    logger.info("Look %s: %d piece(s) tagged", look_id, len(tags.pieces))
    return look_id, tags


def look_tags(look: dict) -> LookTags:
    """A stored look (db.select_look) back as LookTags, to match it again."""
    return LookTags.model_validate({key: look[key] for key in ("title", "summary", "silhouette", "pieces")})


# --- step 2: the recreations -------------------------------------------------------------------
def shortlists(pieces: list[LookPiece], owned: dict[int, Garment]) -> dict[int, list[int]]:
    """For each piece, by its number (from 1), the owned garments most like it on paper."""
    return {number: similar_garments(piece.as_garment(), owned, config.MIMIC_SHORTLIST_LIMIT)
            for number, piece in enumerate(pieces, start=1)}


def look_record(tags: LookTags) -> dict:
    """The look as the matching call sees it: the whole, then each piece by number, with its layer like a garment."""
    pieces = {}
    for number, piece in enumerate(tags.pieces, start=1):
        record = piece.model_dump(mode="json", exclude_none=True)
        layer = layer_for(piece.category, piece.subcategory)
        if layer:
            record["layer"] = layer
        pieces[number] = record
    look = {"title": tags.title, "summary": tags.summary}
    if tags.silhouette:
        look["silhouette"] = f"{tags.silhouette}-line"
    return {**look, "pieces": pieces}


def mimic_context(owned: dict[int, Garment], tags: LookTags, lists: dict[int, list[int]], note: str | None,
                  preferences: str | None, caching: bool = True) -> list[dict]:
    """The matching message: the cached wardrobe first (shared with outfits and weigh), then the look."""
    context = [wardrobe_block(wardrobe_for_prompt(owned), caching)]
    if preferences:
        context.append({"type": "text", "text": f"<preferences>\n{preferences}\n</preferences>"})
    context.append({"type": "text", "text": f"<look>\n{json.dumps(look_record(tags), ensure_ascii=False)}\n</look>"})
    if note:
        context.append({"type": "text", "text": f"<note>\nThe owner's note about the look: {note}\n</note>"})
    lines = []
    for number, ids in lists.items():
        piece = tags.pieces[number - 1]
        lines.append(f"{number} ({piece.primary_color} {piece.subcategory}): " + (", ".join(map(str, ids)) or "(nothing owned in this category)"))
    context.append({"type": "text", "text": "<shortlists>\n" + "\n".join(lines) + "\n</shortlists>"})
    context.append({"type": "text", "text": MIMIC_INSTRUCTIONS})
    return context


def check_matches(recreation: MimicOutfit, pieces: list[LookPiece]) -> tuple[list[str], list[LookMatchOut]]:
    """One match per piece, in order. A stand-in that isn't in the outfit, or already stands in for another
    piece, becomes "none" rather than dropping the outfit; a piece the reply skipped is "none" too."""
    problems: list[str] = []
    in_outfit = {g.garment_id for g in recreation.garments}
    given: dict[int, LookMatchOut] = {}
    used: set[int] = set()
    for match in recreation.matches:
        if not 1 <= match.piece <= len(pieces):
            problems.append(f"match for piece {match.piece}, which isn't in the look")
            continue
        if match.piece in given:
            problems.append(f"piece {match.piece} matched twice; kept the first")
            continue
        garment_id = match.garment_id if match.closeness != "none" and match.garment_id != 0 else None
        if garment_id is not None and garment_id not in in_outfit:
            problems.append(f"piece {match.piece}: stand-in {garment_id} isn't in the outfit")
            garment_id = None
        elif garment_id is not None and garment_id in used:
            problems.append(f"piece {match.piece}: stand-in {garment_id} already stands in for another piece")
            garment_id = None
        if garment_id is None:
            given[match.piece] = LookMatchOut(piece=match.piece, closeness="none", note=match.note.strip() or None)
        else:
            used.add(garment_id)
            given[match.piece] = LookMatchOut(piece=match.piece, garment_id=garment_id, closeness=match.closeness,
                                              note=match.note.strip() or None)
    for number in range(1, len(pieces) + 1):
        if number not in given:
            problems.append(f"piece {number}: no match given")
            given[number] = LookMatchOut(piece=number, closeness="none")
    return problems, [given[number] for number in sorted(given)]


def missing_text(matches: list[LookMatchOut], pieces: list[LookPiece]) -> str | None:
    """The look's pieces nothing owned stands in for, as the photos showed them. Shown as "To finish the look"."""
    unmatched = [pieces[m.piece - 1].description.strip() for m in matches if m.garment_id is None]
    return " ".join(text if text.endswith((".", "。", "!", "?")) else text + "." for text in unmatched if text) or None


def check_recreations(result: MimicResult, pieces: list[LookPiece], owned: dict[int, Garment]
                      ) -> tuple[list[str], list[tuple[Outfit, list[LookMatchOut]]]]:
    """The recreations worth saving, closest first, each as an outfit plus its matches. An outfit that breaks
    the usual outfit rules (unknown garment, no shoes...) is dropped; bad matches are fixed up, not dropped."""
    problems: list[str] = []
    kept: list[tuple[Outfit, list[LookMatchOut]]] = []
    if len(result.outfits) > config.MIMIC_MAX_OUTFITS:
        problems.append(f"{len(result.outfits)} recreations returned; kept the first {config.MIMIC_MAX_OUTFITS}")
    for number, recreation in enumerate(result.outfits[:config.MIMIC_MAX_OUTFITS], start=1):
        outfit = Outfit(aesthetic=recreation.aesthetic.strip(), explanation=recreation.explanation.strip(), garments=recreation.garments)
        outfit_problems = validate_outfit(outfit, owned, None)
        problems += [f"Recreation {number}: {p}" for p in outfit_problems]
        if outfit_problems:
            continue
        match_problems, matches = check_matches(recreation, pieces)
        problems += [f"Recreation {number}: {p}" for p in match_problems]
        kept.append((outfit.model_copy(update={"missing": missing_text(matches, pieces)}), matches))
    return problems, kept


def offline_result(tags: LookTags, owned: dict[int, Garment]) -> MimicResult:
    """-t: the top of each piece's shortlist as its stand-in, so the output shows real garments with no call."""
    matches, garments, used = [], [], set()
    for number, ids in shortlists(tags.pieces, owned).items():
        pick = next((i for i in ids if i not in used), None)
        if pick is None:
            matches.append({"piece": number, "garment_id": 0, "closeness": "none", "note": "nothing similar owned"})
            continue
        used.add(pick)
        garments.append(OutfitGarment(garment_id=pick))
        matches.append({"piece": number, "garment_id": pick, "closeness": "loose", "note": "test mode: top of the shortlist"})
    return MimicResult.model_validate({"outfits": [{"matches": matches, "garments": [g.model_dump() for g in garments],
                                                    "aesthetic": f"{tags.title} (test)", "explanation": "Test mode: no AI call was made."}]})


def recreate(db_path: Path, user_id: int, look_id: int | None, tags: LookTags, note: str | None, client: Anthropic | None,
             log_path: Path, preferences: str | None = None, language: Language = DEFAULT_LANGUAGE, caching: bool = True,
             is_test: bool = False) -> tuple[list[tuple[Outfit, list[LookMatchOut]]], list[int]]:
    """Match the look against the owned wardrobe and save the valid recreations (unless testing).
    Returns the recreations and their new outfit IDs, in the same order."""
    owned = {g.id: g for g in db.select_owned_garments(db_path, user_id)}
    if not owned:
        logger.warning("Look %s: the wardrobe is empty, so there's nothing to match", look_id)
        return [], []

    lists = shortlists(tags.pieces, owned)
    context = mimic_context(owned, tags, lists, note, preferences, caching)
    usage: TokenUsage | None = None
    if is_test:
        result = offline_result(tags, owned)
    else:
        try:
            result, usage = match_look(client, context, language)
        except UnusableResponse as error:
            log_failed_call(log_path, user_id, error.usage, str(error))
            raise

    problems, kept = check_recreations(result, tags.pieces, owned)
    for problem in problems:
        logger.warning("Mimic validation: %s", problem)

    timestamp = _now()
    outfit_ids: list[int] = []
    if not is_test and look_id is not None and kept:
        outfit_ids = db.insert_outfits(db_path, user_id, [outfit for outfit, _ in kept], None, REQUEST_PREFIX + tags.title,
                                       timestamp, look_id=look_id)
        for outfit_id, (_, matches) in zip(outfit_ids, kept):
            db.insert_look_matches(db_path, outfit_id, matches)
    if not is_test:
        _log(log_path, {"timestamp": timestamp, "user_id": user_id, "kind": "match-look", "look_id": look_id,
                        "outfit_ids": outfit_ids, "usage": usage.model_dump() if usage else None,
                        "result": result.model_dump(mode="json"), "context": "\n".join(block["text"] for block in context),
                        "problems": problems})
    return kept, outfit_ids
