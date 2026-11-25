import logging
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Iterator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from contextlib import asynccontextmanager, contextmanager

from enclothed import config, db, demo, drafts, mend, mimic, photos, preferences, responses, reworks, shares, weigh
from enclothed.auth import ACT_AS_COOKIE, current_user, signed_in_user
# Paths are read as config.NAME when used, not imported here, so a test can move them all by patching config alone.
from enclothed.config import (
    DEMO_DAILY_REWORK_LIMIT, DEMO_DAILY_TOKEN_LIMIT, MANUAL_OUTFIT_REQUEST, UPLOAD_MAX_BYTES, UPLOAD_MAX_PHOTOS, DEMO_SHARE_LIMIT,
    SHARE_MAX_LIFETIME_DAYS, MODEL_NAMES, MODELS_BY_PROVIDER, PROVIDER_NAMES,
)
from enclothed.models import (
    ActAsIn, Garment, GarmentOut, LanguageIn, OptionsOut, Outfit, OutfitCreateIn, OutfitDescribeIn, OutfitDescription, OutfitGarment, OutfitLikedIn, OutfitOut, WearIn,
    OutfitSuggestIn, PreferencesImproveIn, PreferencesIn, PreferencesOut, ProfileOut, SetOut, UsageAllOut, UsageCall,
    User, UserOut, InsightsIn, InsightsOut, DraftOut, MendOut, WeighCreatedOut, WeighIn, WeighOut, blank_fields,
    LookOut, MimicCreatedOut, Language, ShareCreatedOut, ShareIn, ShareOut, LLMModelOut, LLMOut, ReworkAllowanceOut, ReworkIn, ReworkOut,
)
from enclothed.insights import answer_question
from enclothed.llm import Client, NotConfigured, ServiceError, UnusableResponse, active_provider, make_client
from enclothed.outfit import fill_description, generate_outfits
from enclothed.usage import log_failed_call, read_calls

load_dotenv()

CurrentUser = Annotated[User, Depends(current_user)]
SignedInUser = Annotated[User, Depends(signed_in_user)]
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts: create the DB if it's new, apply any pending migrations."""
    db.init_db(config.DB_PATH, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    shares.purge_expired(config.DB_PATH, config.SHARES_DIR, datetime.now(timezone.utc))
    shares.remove_orphaned_photos(config.DB_PATH, config.SHARES_DIR)
    reworks.remove_orphaned_files(config.DB_PATH, config.REWORKS_DIR)
    yield


app = FastAPI(title="enclothed", lifespan=lifespan)


class RevalidatedStaticFiles(StaticFiles):
    """Page files the browser must re-check before reusing, so updates show up on a normal refresh."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


config.GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", RevalidatedStaticFiles(directory=config.PUBLIC_DIR), name="static")  # the page's CSS
# The same files for share links. Everything a shared page loads is under /s/, so Cloudflare Access needs
# only one path open to everyone. Mounted before the routes, so /s/static/... never reaches /s/{token}/...
app.mount("/s/static", RevalidatedStaticFiles(directory=config.PUBLIC_DIR), name="share-static")


def _llm_client(provider: str | None = None) -> Client:
    """The LLM client (for provider, or the default when that's None), or a 503 explaining why AI is unavailable."""
    try:
        return make_client(provider)
    except NotConfigured as error:
        raise HTTPException(status_code=503, detail=str(error))


def _chosen_provider(me: SignedInUser, choice: Annotated[str | None, Header(alias="X-LLM-Provider")] = None) -> str | None:
    """The LLM an admin picked for this browser tab (hold L and click an AI button; see features/llmPicker.js).
    Anyone else's choice is ignored, so they always get the default."""
    if not choice or not me.is_admin:
        return None
    if choice not in MODELS_BY_PROVIDER:
        raise HTTPException(status_code=422, detail=f"There's no LLM provider named {choice!r}.")
    return choice


ChosenProvider = Annotated[str | None, Depends(_chosen_provider)]


def _require_demo_tokens(user: User) -> None:
    """Stop AI calls from the demo once today's limit is spent. Real wardrobes have no limit here."""
    if user.is_demo and demo.tokens_used(_usage_logs(), user.id) >= DEMO_DAILY_TOKEN_LIMIT:
        raise HTTPException(status_code=429, detail="The demo has used up today's AI allowance. It resets overnight.")


@contextmanager
def _ai_errors(user: User, log_path: Path, unusable: str) -> Iterator[None]:
    """Turn a failed AI call inside the block into a 502 for the page, with unusable as its message when the AI
    answered with nothing usable. A refused or unanswered call is logged here, to that feature's log, so it's on
    record outside docker logs. An unusable answer was billed, so the feature logs it itself, with its tokens."""
    try:
        yield
    except ServiceError as error:
        logger.exception("LLM call failed")
        log_failed_call(log_path, user.id, None, f"{error.kind}: {error.message}", error.request_id)
        raise HTTPException(status_code=502, detail=f"The AI service failed: {error.message}. Nothing was saved; try again.")
    except UnusableResponse:
        logger.exception("LLM gave no usable answer")
        raise HTTPException(status_code=502, detail=unusable)


def _blank_to_none(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


# --- garments -----------------------
@app.get("/api/garments")
def list_garments(user: CurrentUser) -> list[GarmentOut]:
    return responses.list_garments(config.DB_PATH, user.id)


@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int, user: CurrentUser) -> GarmentOut:
    garment = responses.get_garment(config.DB_PATH, user.id, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment


def _drafts_dir() -> Path:
    return config.INTAKE_DIR / "drafts"


def _saved_preferences(user: User) -> str | None:
    saved = db.select_preferences(config.DB_PATH, user.id)
    return saved[0] if saved else None


def _stage_uploads(uploads: list[UploadFile], tmp_dir: Path) -> list[Path]:
    """Save each upload in tmp_dir as an upright JPEG the API accepts, or raise the error saying which one can't be used."""
    paths = []
    for index, upload in enumerate(uploads):
        raw = tmp_dir / f"raw_{index:02d}"
        with raw.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        if raw.stat().st_size > UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"“{upload.filename}” is larger than {UPLOAD_MAX_BYTES // (1024 * 1024)} MB.")
        photo = tmp_dir / f"{index:02d}.jpg"
        try:
            photos.normalize_photo(raw, photo)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"“{upload.filename}” isn't a photo that can be read.")
        paths.append(photo)
    return paths


@app.post("/api/garments/drafts", status_code=201)
def tag_new_garment(
    user: CurrentUser,
    provider: ChosenProvider,
    photos_in: list[UploadFile] = File(alias="photos"),
    prompt_message: str | None = Form(None),
    notes: str | None = Form(None),
) -> DraftOut:
    """Tag uploaded photos (front, back, labels...) and hold the result for review. Nothing joins the wardrobe yet."""
    if not 1 <= len(photos_in) <= UPLOAD_MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"Send between 1 and {UPLOAD_MAX_PHOTOS} photos.")
    _require_demo_tokens(user)
    client = _llm_client(provider)

    _drafts_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=config.INTAKE_DIR, prefix="upload-", ignore_cleanup_errors=True) as tmp:
        paths = _stage_uploads(photos_in, Path(tmp))
        with _ai_errors(user, config.TAGGING_LOG_PATH, "The AI couldn't tag these photos. Nothing was saved; try again."):
            draft = drafts.create_draft(_drafts_dir(), user.id, paths, config.TAGGING_LOG_PATH, client, _blank_to_none(prompt_message),
                                        _blank_to_none(notes), user.language, _saved_preferences(user))

    return DraftOut(id=draft.id, garment=draft.garment)


@app.post("/api/garments/drafts/{draft_id}", status_code=201)
def accept_draft(draft_id: str, garment: Garment, user: CurrentUser) -> GarmentOut:
    """Add a reviewed garment to the wardrobe, with any changes the owner made."""
    garment_id = drafts.confirm_draft(_drafts_dir(), config.DB_PATH, config.GARMENTS_DIR, config.TAGGING_LOG_PATH, user.id, draft_id, garment)
    if garment_id is None:
        raise HTTPException(status_code=404, detail="That garment is no longer waiting for review. Add it again.")
    return responses.get_garment(config.DB_PATH, user.id, garment_id)


@app.delete("/api/garments/drafts/{draft_id}", status_code=204)
def discard_draft(draft_id: str, user: CurrentUser) -> None:
    """Delete the draft and its photos. A draft that's already gone is fine: the owner wanted it gone."""
    drafts.discard_draft(_drafts_dir(), user.id, draft_id)


@app.post("/api/garments/{garment_id}/mend")
def mend_garment(garment_id: int, user: CurrentUser, provider: ChosenProvider) -> MendOut:
    """Ask the LLM for this garment's blank fields, for the owner to review. Saves none of its answers."""
    _require_demo_tokens(user)
    garment = db.select_garment(config.DB_PATH, user.id, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    if not blank_fields(garment):
        raise HTTPException(status_code=422, detail="This garment has no blank fields.")
    client = _llm_client(provider)

    try:
        with _ai_errors(user, config.TAGGING_LOG_PATH, "The AI couldn't fill these in. Nothing was saved; try again."):
            result = mend.mend_garment(config.DB_PATH, config.TAGGING_LOG_PATH, user.id, garment, client, user.language, _saved_preferences(user))
    except mend.NoPhotos as error:
        raise HTTPException(status_code=422, detail=str(error))
    return MendOut(filled=result.filled, unanswered=result.unanswered)


def _require_garment(user: User, garment_id: int, not_found: str | None = None) -> None:
    """A 404 unless the garment is the user's. not_found replaces the message, as for a photo."""
    if db.select_garment(config.DB_PATH, user.id, garment_id) is None:
        raise HTTPException(status_code=404, detail=not_found or f"Garment {garment_id} not found")


# --- rework (#74): an edited copy of a garment's photo -----
@app.post("/api/garments/{garment_id}/reworks", status_code=201)
def rework_garment(garment_id: int, body: ReworkIn, user: CurrentUser) -> ReworkOut:
    """Edit the garment's front photo by the instruction and keep the result. Always OpenAI: Claude makes no images,
    so the admin's LLM choice doesn't apply."""
    _require_garment(user, garment_id)
    if user.is_demo and demo.reworks_used(config.REWORK_LOG_PATH, user.id) >= DEMO_DAILY_REWORK_LIMIT:
        raise HTTPException(status_code=429, detail=f"The demo has used today's {DEMO_DAILY_REWORK_LIMIT} reworks. They reset overnight.")
    client = _llm_client("openai")
    try:
        rework = reworks.rework_garment(config.DB_PATH, config.REWORKS_DIR, config.REWORK_LOG_PATH, user.id, garment_id, body.instruction, client)
    except reworks.NoPhotos as error:
        raise HTTPException(status_code=422, detail=str(error))
    except ServiceError as error:
        logger.exception("Rework call failed")
        reworks.log_call(config.REWORK_LOG_PATH, user.id, garment_id, None, error=f"{error.kind}: {error.message}")
        raise HTTPException(status_code=502, detail=f"The AI service failed: {error.message}. Nothing was saved; try again.")
    except UnusableResponse:
        logger.exception("Rework gave no image")
        raise HTTPException(status_code=502, detail="The AI didn't send back an image. Nothing was saved; try again.")
    return responses.to_rework_out(rework)


@app.get("/api/garments/{garment_id}/reworks")
def list_reworks(garment_id: int, user: CurrentUser) -> list[ReworkOut]:
    """The garment's reworks, newest first."""
    _require_garment(user, garment_id)
    return responses.list_reworks(config.DB_PATH, user.id, garment_id)


@app.get("/api/reworks/allowance")
def rework_allowance(user: CurrentUser) -> ReworkAllowanceOut:
    """For the Rework panel's "2 of 3 left today" in the demo."""
    if not user.is_demo:
        return ReworkAllowanceOut(left=None)
    return ReworkAllowanceOut(left=max(0, DEMO_DAILY_REWORK_LIMIT - demo.reworks_used(config.REWORK_LOG_PATH, user.id)))


@app.delete("/api/reworks/{rework_id}", status_code=204)
def delete_rework(rework_id: int, user: CurrentUser) -> None:
    if not reworks.delete(config.DB_PATH, config.REWORKS_DIR, user.id, rework_id):
        raise HTTPException(status_code=404, detail=f"Rework {rework_id} not found")


EDITABLE_FIELDS = set(Garment.model_fields) - {"id", "date_added", "set_id", "mended_on", "user_id", "weighed_on"}   # weigh has its own buy endpoint

@app.patch("/api/garments/{garment_id}")
def edit_garment(garment_id: int, changes: dict[str, Any], user: CurrentUser) -> GarmentOut:
    garment = db.select_garment(config.DB_PATH, user.id, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")

    not_editable = changes.keys() - EDITABLE_FIELDS
    if not_editable:
        raise HTTPException(status_code=422, detail=f"Can't edit: {sorted(not_editable)}")

    try:
        edited = Garment.model_validate({**garment.model_dump(), **changes})
    except ValidationError as error:
        raise RequestValidationError(error.errors(include_url=False, include_input=False))

    db.update_garment(config.DB_PATH, user.id, edited)
    return responses.to_garment_out(edited)


# --- weigh: should I buy this? (#2) -------
@app.post("/api/weighs", status_code=201)
def weigh_garment(body: WeighIn, user: CurrentUser, provider: ChosenProvider) -> WeighCreatedOut:
    """Weigh a tagged, reviewed draft against the wardrobe. Saves it as a candidate, not as owned.
    If the AI call fails, the draft is left as it was, so trying again doesn't re-tag the photos."""
    _require_demo_tokens(user)
    client = _llm_client(provider)
    try:
        with _ai_errors(user, config.WEIGH_LOG_PATH, "The AI couldn't weigh this garment. Nothing was saved; try again."):
            saved, garment_id, outfit_ids = weigh.weigh_draft(
                config.DB_PATH, _drafts_dir(), config.GARMENTS_DIR, config.TAGGING_LOG_PATH, config.WEIGH_LOG_PATH, user.id, body.draft_id, body.garment, client,
                _saved_preferences(user), user.language)
    except weigh.DraftGone:
        raise HTTPException(status_code=404, detail="That garment is no longer waiting. Photograph it again.")
    return WeighCreatedOut(weigh=saved, candidate=responses.get_garment(config.DB_PATH, user.id, garment_id),
                           outfits=responses.get_outfits(config.DB_PATH, user.id, outfit_ids))


@app.get("/api/weighs")
def list_weighs(user: CurrentUser) -> list[WeighOut]:
    """Verdicts for garments still being weighed. The garments and outfits come with the usual lists."""
    return db.select_weighs(config.DB_PATH, user.id)


@app.post("/api/weighs/{garment_id}/buy")
def buy_weighed(garment_id: int, user: CurrentUser) -> GarmentOut:
    """I bought it: the candidate joins the wardrobe as it is, photos and outfits included."""
    if not db.buy_candidate(config.DB_PATH, user.id, garment_id):
        raise HTTPException(status_code=404, detail=f"No garment {garment_id} is being weighed")
    return responses.get_garment(config.DB_PATH, user.id, garment_id)


@app.delete("/api/weighs/{garment_id}", status_code=204)
def discard_weighed(garment_id: int, user: CurrentUser) -> None:
    """Not buying: delete the candidate, its photos, its verdict and the outfits suggested with it."""
    if not db.delete_candidate(config.DB_PATH, user.id, garment_id):
        raise HTTPException(status_code=404, detail=f"No garment {garment_id} is being weighed")
    photos.delete_garment_photos(garment_id)


# --- mimic: recreate a photographed look (#5) -------
# Two requests, which the page sends one after the other: each AI call gets its own, so neither runs into the
# proxy's 100-second limit, and the page can say which step it's on. A look whose matching failed, or never
# ran because the browser closed, keeps its photos and tags, and its page offers to match it again.
MATCH_FAILED = "The AI couldn't match this look to your wardrobe. The look is saved; try matching it again."


@app.post("/api/looks", status_code=201)
def create_look(
    user: CurrentUser,
    provider: ChosenProvider,
    photos_in: list[UploadFile] = File(alias="photos"),
    note: str | None = Form(None),
) -> LookOut:
    """Step 1: break a photographed look down into its pieces and save it. The only call that sees the photos."""
    if not 1 <= len(photos_in) <= UPLOAD_MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"Send between 1 and {UPLOAD_MAX_PHOTOS} photos.")
    _require_demo_tokens(user)
    client = _llm_client(provider)

    config.INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=config.INTAKE_DIR, prefix="look-", ignore_cleanup_errors=True) as tmp:
        paths = _stage_uploads(photos_in, Path(tmp))
        with _ai_errors(user, config.MIMIC_LOG_PATH, "The AI couldn't make out the look in these photos. Nothing was saved; try again."):
            look_id, _ = mimic.create_look(config.DB_PATH, user.id, paths, _blank_to_none(note), client, user.language, config.MIMIC_LOG_PATH)
    return responses.get_look(config.DB_PATH, user.id, look_id)


@app.get("/api/looks")
def list_looks(user: CurrentUser) -> list[LookOut]:
    return responses.list_looks(config.DB_PATH, user.id)


@app.post("/api/looks/{look_id}/recreations", status_code=201)
def recreate_look(look_id: int, user: CurrentUser, provider: ChosenProvider) -> MimicCreatedOut:
    """Step 2: recreate a saved look from the wardrobe, as up to two outfits, closest first, each with the owned
    stand-in for every piece and how close it is. Text only. Refused once the look has recreations."""
    look = db.select_look(config.DB_PATH, user.id, look_id)
    if look is None:
        raise HTTPException(status_code=404, detail=f"Look {look_id} not found")
    if look["recreations"]:
        raise HTTPException(status_code=409, detail="This look already has its recreations.")
    _require_demo_tokens(user)
    client = _llm_client(provider)
    with _ai_errors(user, config.MIMIC_LOG_PATH, MATCH_FAILED):
        _, outfit_ids = mimic.recreate(config.DB_PATH, user.id, look_id, mimic.look_tags(look), look["note"], client, config.MIMIC_LOG_PATH,
                                       _saved_preferences(user), user.language)
    return MimicCreatedOut(look=responses.get_look(config.DB_PATH, user.id, look_id),
                           outfits=responses.get_outfits(config.DB_PATH, user.id, outfit_ids))


@app.delete("/api/looks/{look_id}", status_code=204)
def delete_look(look_id: int, user: CurrentUser) -> None:
    """Delete a look and its photos. Its outfits stay, as ordinary outfits."""
    if not db.delete_look(config.DB_PATH, user.id, look_id):
        raise HTTPException(status_code=404, detail=f"Look {look_id} not found")
    photos.delete_look_photos(look_id)


# --- outfits -------------------------
@app.get("/api/outfits")
def list_outfits(user: CurrentUser) -> list[OutfitOut]:
    return responses.list_outfits(config.DB_PATH, user.id)


@app.get("/api/outfits/{outfit_id}")
def get_outfit(outfit_id: int, user: CurrentUser) -> OutfitOut:
    outfit = responses.get_outfit(config.DB_PATH, user.id, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return outfit


def _styling_wardrobe(user: User, ids: list[int]) -> dict[int, Garment]:
    """Garments an outfit can use: everything owned, plus any garment being weighed that the request names.
    A weigh verdict's outfit links open the candidate with owned pieces in the builder, which then generates,
    describes or saves around it. The candidate only joins when named, so outfits never pull it in uninvited."""
    wardrobe = {g.id: g for g in db.select_owned_garments(config.DB_PATH, user.id)}
    for garment_id in ids:
        if garment_id not in wardrobe:
            garment = db.select_garment(config.DB_PATH, user.id, garment_id)
            if garment and garment.weighed_on and not garment.disowned_on:
                wardrobe[garment_id] = garment
    return wardrobe


@app.post("/api/outfits/suggestions")
def suggest_outfits(body: OutfitSuggestIn, user: CurrentUser, provider: ChosenProvider) -> list[OutfitOut]:
    """Ask the LLM for outfits built around the anchors and details; returns only the new, valid ones."""
    details = _blank_to_none(body.details)
    anchors = list(dict.fromkeys(body.anchors))
    if not anchors and not details:
        raise HTTPException(status_code=422, detail="Add at least one piece or some details.")

    wardrobe = _styling_wardrobe(user, anchors)
    unknown = [i for i in anchors if i not in wardrobe]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Garment(s) not found: {unknown}")

    _require_demo_tokens(user)
    client = _llm_client(provider)
    with _ai_errors(user, config.OUTFIT_LOG_PATH, "The AI couldn't suggest outfits. Nothing was saved; try again."):
        _, new_ids = generate_outfits(config.DB_PATH, user.id, wardrobe, anchors or None, config.OUTFIT_LOG_PATH, client,
                                      details or "everyday wear", False, preferences=_saved_preferences(user),
                                      language=user.language, count=body.count, riskiness=body.riskiness,
                                      silhouette=body.silhouette)
    return responses.get_outfits(config.DB_PATH, user.id, new_ids)


@app.post("/api/outfits", status_code=201)
def create_outfit(body: OutfitCreateIn, user: CurrentUser) -> OutfitOut:
    """Save an outfit the user put together themselves, without the LLM."""
    ids = [g.garment_id for g in body.garments]
    if len(set(ids)) < len(ids):
        raise HTTPException(status_code=422, detail="The same garment is in the outfit twice.")
    known = _styling_wardrobe(user, ids)
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Garment(s) not found: {unknown}")

    outfit = Outfit(
        aesthetic=body.aesthetic,
        explanation=body.explanation,
        missing=_blank_to_none(body.missing),
        garments=[OutfitGarment(garment_id=g.garment_id, styling_advice=_blank_to_none(g.styling_advice)) for g in body.garments],
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    [outfit_id] = db.insert_outfits(config.DB_PATH, user.id, [outfit], None, _blank_to_none(body.details) or MANUAL_OUTFIT_REQUEST, timestamp, source="own")
    return responses.get_outfit(config.DB_PATH, user.id, outfit_id)


@app.post("/api/outfits/describe")
def describe_own_outfit(body: OutfitDescribeIn, user: CurrentUser, provider: ChosenProvider) -> OutfitDescription:
    """Fill in a blank name or explanation for an outfit the user is putting together. Saves nothing."""
    ids = list(dict.fromkeys(body.garments))
    wardrobe = _styling_wardrobe(user, ids)
    unknown = [i for i in ids if i not in wardrobe]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Garment(s) not found: {unknown}")

    aesthetic, explanation = _blank_to_none(body.aesthetic), _blank_to_none(body.explanation)
    if aesthetic and explanation:
        return OutfitDescription(aesthetic=aesthetic, explanation=explanation)  # nothing to fill, so no tokens

    _require_demo_tokens(user)
    client = _llm_client(provider)
    with _ai_errors(user, config.OUTFIT_LOG_PATH, "The AI couldn't describe this outfit. Try again, or write it yourself."):
        return fill_description(config.OUTFIT_LOG_PATH, user.id, {i: wardrobe[i] for i in ids}, client, _blank_to_none(body.details),
                                aesthetic, explanation, _saved_preferences(user), user.language)


@app.patch("/api/outfits/{outfit_id}")
def edit_outfit_liked(outfit_id: int, body: OutfitLikedIn, user: CurrentUser) -> OutfitOut:
    if not db.set_outfit_liked(config.DB_PATH, user.id, outfit_id, body.liked):
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return responses.get_outfit(config.DB_PATH, user.id, outfit_id)


@app.post("/api/outfits/{outfit_id}/wears", status_code=201)
def log_wear(outfit_id: int, body: WearIn, user: CurrentUser) -> OutfitOut:
    """Record that the user wore this outfit, on body.worn_on (today by default). Returns the outfit with its wears."""
    day = body.worn_on or date.today()
    if day > date.today() + timedelta(days=1):   # a day of slack: the browser's today can be ahead of the server's
        raise HTTPException(status_code=422, detail="That date hasn't happened yet.")
    if db.insert_wear(config.DB_PATH, user.id, outfit_id, day, _blank_to_none(body.notes)) is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return responses.get_outfit(config.DB_PATH, user.id, outfit_id)


@app.delete("/api/outfits/{outfit_id}/wears/{wear_id}")
def remove_wear(outfit_id: int, wear_id: int, user: CurrentUser) -> OutfitOut:
    """Undo a wear logged by mistake. Returns the outfit with its remaining wears."""
    if not db.delete_wear(config.DB_PATH, user.id, outfit_id, wear_id):
        raise HTTPException(status_code=404, detail=f"Wear {wear_id} not found on outfit {outfit_id}")
    return responses.get_outfit(config.DB_PATH, user.id, outfit_id)


# --- share links ---------------------
@app.post("/api/shares", status_code=201)
def create_share(body: ShareIn, user: CurrentUser) -> ShareCreatedOut:
    """A new link to a frozen copy of one garment, or one outfit and its garments, for anyone to view for a few days."""
    make = shares.share_garment if body.kind == "garment" else shares.share_outfit
    limit = DEMO_SHARE_LIMIT if user.is_demo else None
    try:
        made = make(config.DB_PATH, config.SHARES_DIR, user.id, body.id, user.language, datetime.now(timezone.utc), limit)
    except shares.ShareLimitReached:
        raise HTTPException(status_code=409, detail=f"The demo already has {DEMO_SHARE_LIMIT} live share links. "
                                                    "Try again once one expires or is revoked.")
    if made is None:
        raise HTTPException(status_code=404, detail=f"{body.kind.capitalize()} {body.id} not found")
    token, expires_at = made
    return ShareCreatedOut(path=f"/s/{token}", expires_at=expires_at)


@app.delete("/api/shares/{token}", status_code=204)
def revoke_share(token: str, user: CurrentUser) -> None:
    """End one of your live links now. Someone else's, or one that has expired, is a 404 like a wrong token."""
    if not shares.revoke(config.DB_PATH, config.SHARES_DIR, user.id, token, datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail="That link has expired or doesn't exist.")


@app.post("/api/shares/{token}/extend")
def extend_share(token: str, user: CurrentUser) -> ShareOut:
    """Make one of your live links last 72 hours from now, up to 12 days after it was made."""
    now = datetime.now(timezone.utc)
    try:
        extended = shares.extend(config.DB_PATH, user.id, token, now)
    except shares.ShareAtMaxLifetime:
        raise HTTPException(status_code=409, detail=f"This link already lasts the longest a link can: "
                                                    f"{SHARE_MAX_LIFETIME_DAYS} days from when it was made.")
    share = responses.get_share(config.DB_PATH, user.id, token, now.isoformat(timespec="seconds")) if extended else None
    if share is None:
        raise HTTPException(status_code=404, detail="That link has expired or doesn't exist.")
    return share


@app.get("/api/shares")
def list_shares(user: CurrentUser) -> list[ShareOut]:
    """Your live share links, newest first. In the demo, every visitor's links."""
    return responses.list_shares(config.DB_PATH, user.id, _now())


# --- preferences ---------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/api/preferences")
def get_preferences(user: CurrentUser) -> PreferencesOut:
    saved = db.select_preferences(config.DB_PATH, user.id)
    return PreferencesOut(text=saved[0], updated_at=saved[1]) if saved else PreferencesOut()


@app.put("/api/preferences")
def put_preferences(body: PreferencesIn, user: CurrentUser) -> PreferencesOut:
    """Save the user's style preferences (sent with every outfit request). Empty text clears them."""
    db.save_preferences(config.DB_PATH, user.id, _blank_to_none(body.text), _now())
    return get_preferences(user)


@app.post("/api/preferences/improve")
def improve_preferences_text(body: PreferencesImproveIn, user: CurrentUser, provider: ChosenProvider) -> PreferencesIn:
    """Ask the LLM to rewrite the text into a clearer brief. Returns the rewrite; saves nothing."""
    _require_demo_tokens(user)
    client = _llm_client(provider)
    with _ai_errors(user, config.PREFERENCES_LOG_PATH, "The AI couldn't rewrite this. Nothing was saved; try again."):
        text = preferences.rewrite(client, config.PREFERENCES_LOG_PATH, user.id, body.text)
    return PreferencesIn(text=text)


# --- insights ------------------------
@app.post("/api/insights")
def ask_insights(body: InsightsIn, user: CurrentUser, provider: ChosenProvider) -> InsightsOut:
    """Answer a question about this wardrobe. The browser keeps the conversation and sends it as history."""
    _require_demo_tokens(user)
    client = _llm_client(provider)
    history = [message.model_dump() for message in body.history]
    with _ai_errors(user, config.INSIGHTS_LOG_PATH, "I couldn't work that out. Try asking it a different way."):
        result = answer_question(client, config.DB_PATH, user.id, body.question, history, user.language,
                                 _saved_preferences(user), config.INSIGHTS_LOG_PATH)
    return InsightsOut(answer=result.answer, queries=result.queries)


# --- sets ----------------------------
@app.get("/api/sets")
def list_sets(user: CurrentUser) -> list[SetOut]:
    return responses.list_sets(config.DB_PATH, user.id)


# --- options -------------------------
@app.get("/api/options")
def get_options(user: CurrentUser) -> OptionsOut:
    return responses.get_options(user.language)


# --- profile -------------------------
@app.get("/api/llms")
def list_llms(me: SignedInUser) -> list[LLMOut]:
    """The LLMs an admin can pick for a browser tab, with the models each one runs for each feature."""
    _require_admin(me)
    default = active_provider()
    options = []
    for provider, models in MODELS_BY_PROVIDER.items():
        by_model: dict[str, list[str]] = {}
        for feature, model in models.items():
            by_model.setdefault(model, []).append(feature)
        options.append(LLMOut(provider=provider, name=PROVIDER_NAMES.get(provider, provider), is_default=provider == default,
                              models=[LLMModelOut(id=m, name=MODEL_NAMES.get(m, m), features=f) for m, f in by_model.items()]))
    return options


@app.get("/api/profile")
def get_profile(user: CurrentUser, me: SignedInUser) -> ProfileOut:
    """Whose wardrobe is showing, and what the page should offer the person looking at it."""
    demo_user = db.select_demo_user(config.DB_PATH)
    return ProfileOut(name=user.username, language=user.language, is_admin=me.is_admin,
                      signed_in_as=me.username if me.id != user.id else None,
                      is_demo=user.is_demo,
                      demo_user_id=demo_user.id if demo_user and demo_user.demo_reset_at else None)


@app.put("/api/language", status_code=204)
def put_language(body: LanguageIn, user: CurrentUser, me: SignedInUser) -> None:
    """Set the language of this wardrobe's fixed terms and of what the LLM writes for it from now on.

    In the shared demo this is your own setting, since the demo uses each visitor's language.
    """
    db.set_language(config.DB_PATH, me.id if user.is_demo else user.id, body.language)


# --- usage ---------------------------
DateParam = Annotated[datetime | None, Query()]
FromParam = Annotated[datetime | None, Query(alias="from")]


def _usage_logs() -> dict[str, Path]:
    return {"tagging": config.TAGGING_LOG_PATH, "outfits": config.OUTFIT_LOG_PATH, "style": config.PREFERENCES_LOG_PATH, "insights": config.INSIGHTS_LOG_PATH, "weigh": config.WEIGH_LOG_PATH,
            "mimic": config.MIMIC_LOG_PATH, "rework": config.REWORK_LOG_PATH}


@app.get("/api/usage")
def get_usage(user: CurrentUser, from_: FromParam = None, to: DateParam = None) -> list[UsageCall]:
    """This person's LLM calls, oldest first. to is exclusive."""
    return [call for call in read_calls(_usage_logs(), from_, to) if call.user_id == user.id]


@app.get("/api/usage/all")
def get_all_usage(me: SignedInUser, from_: FromParam = None, to: DateParam = None) -> UsageAllOut:
    """Everyone's LLM calls, for an admin. Goes by who's signed in, so it doesn't change while acting as someone."""
    _require_admin(me)
    return UsageAllOut(users=list_users(me), calls=read_calls(_usage_logs(), from_, to))


# --- acting as another user ----------
def _require_admin(me: User) -> None:
    if not me.is_admin:
        raise HTTPException(status_code=403, detail="Only an admin can do this")


@app.get("/api/users")
def list_users(me: SignedInUser) -> list[UserOut]:
    _require_admin(me)
    return [UserOut(id=user.id, username=user.username) for user in db.select_all_users(config.DB_PATH)]


@app.put("/api/act-as", status_code=204)
def act_as(body: ActAsIn, me: SignedInUser, response: Response) -> None:
    """Switch wardrobes. Anyone can open the shared demo; only an admin can open someone else's.
    No user id, or your own, goes back to yours."""
    if body.user_id is None or body.user_id == me.id:
        response.delete_cookie(ACT_AS_COOKIE)
        return
    target = db.select_user(config.DB_PATH, body.user_id)
    if target is None or not target.is_demo:
        _require_admin(me)
    if target is None:
        raise HTTPException(status_code=404, detail=f"User {body.user_id} not found")
    response.set_cookie(ACT_AS_COOKIE, str(body.user_id), httponly=True, samesite="lax")


# --- photos and thumbnails -----------
# "private" keeps these out of Cloudflare's cache. A cached copy would be served to the next
# signed-in person without reaching the ownership check here.
PHOTO_CACHING = {"Cache-Control": "private, max-age=3600"}

def _photo_response(path: Path | None) -> FileResponse:
    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, headers=PHOTO_CACHING)


@app.get("/photos/{garment_id}/{filename}", include_in_schema=False)
def get_photo(garment_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_garment(user, garment_id, "Photo not found")
    return _photo_response(photos.get_photo(garment_id, filename))


@app.get("/thumbs/{garment_id}/{filename}", include_in_schema=False)
def get_thumbnail(garment_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_garment(user, garment_id, "Photo not found")
    return _photo_response(photos.get_thumbnail(garment_id, filename))


@app.get("/reworks/{rework_id}", include_in_schema=False)
def get_rework_image(rework_id: int, user: CurrentUser) -> FileResponse:
    if db.select_rework(config.DB_PATH, user.id, rework_id) is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = reworks.image_path(config.REWORKS_DIR, rework_id)
    return _photo_response(path if path.is_file() else None)


def _require_look(user: User, look_id: int) -> None:
    if db.select_look(config.DB_PATH, user.id, look_id) is None:
        raise HTTPException(status_code=404, detail="Photo not found")


@app.get("/looks/{look_id}/thumbs/{filename}", include_in_schema=False)
def get_look_thumbnail(look_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_look(user, look_id)
    return _photo_response(photos.get_look_thumbnail(look_id, filename))


@app.get("/looks/{look_id}/{filename}", include_in_schema=False)
def get_look_photo(look_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_look(user, look_id)
    return _photo_response(photos.get_look_photo(look_id, filename))


# --- shared pages: open to anyone with the link, so nothing here uses the sign-in ---------
# Cloudflare Access lets /s/ through without signing in (see the deployment notes). These routes read only
# the shares table and its photo copies, never the wardrobe. noindex keeps the pages out of search engines;
# no-referrer keeps the link out of other sites' logs.
SHARE_HEADERS = {"Cache-Control": "no-cache", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}
SHARE_PHOTO_HEADERS = {**PHOTO_CACHING, "X-Robots-Tag": "noindex"}


@app.get("/s/options/{language}", include_in_schema=False)
def get_share_options(language: Language) -> OptionsOut:
    """The fixed terms in any language, for a shared page's language menu. App constants, not anyone's data."""
    return responses.get_options(language)


@app.get("/s/{token}", include_in_schema=False)
def share_page(token: str) -> FileResponse:
    """The shared page. It loads its copy from /s/{token}/data, and says so itself when the link has expired."""
    live = shares.load(config.DB_PATH, token, datetime.now(timezone.utc)) is not None
    return FileResponse(config.PUBLIC_DIR / "share.html", status_code=200 if live else 404, headers=SHARE_HEADERS)


@app.get("/s/{token}/data", include_in_schema=False)
def share_data(token: str, response: Response) -> dict:
    snapshot = shares.load(config.DB_PATH, token, datetime.now(timezone.utc))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="This link has expired or doesn't exist.")
    response.headers.update(SHARE_HEADERS)
    return snapshot


def _share_photo(token: str, garment: int, filename: str, small: bool) -> FileResponse:
    path = shares.photo(config.DB_PATH, config.SHARES_DIR, token, garment, filename, small, datetime.now(timezone.utc))
    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, headers=SHARE_PHOTO_HEADERS)


@app.get("/s/{token}/photos/{garment}/{filename}", include_in_schema=False)
def share_photo(token: str, garment: int, filename: str) -> FileResponse:
    return _share_photo(token, garment, filename, small=False)


@app.get("/s/{token}/thumbs/{garment}/{filename}", include_in_schema=False)
def share_thumbnail(token: str, garment: int, filename: str) -> FileResponse:
    return _share_photo(token, garment, filename, small=True)


# --- front end -----------------------
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.PUBLIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
