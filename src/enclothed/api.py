import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from contextlib import asynccontextmanager

from enclothed import db, demo, photos, responses
from enclothed.auth import ACT_AS_COOKIE, current_user, signed_in_user
from enclothed.config import (
    DB_PATH, DEMO_DAILY_TOKEN_LIMIT, GARMENTS_DIR, INTAKE_DIR, MANUAL_OUTFIT_REQUEST, OUTFIT_LOG_PATH, PREFERENCES_LOG_PATH, PUBLIC_DIR,
    TAGGING_LOG_PATH, UPLOAD_MAX_BYTES, UPLOAD_MAX_PHOTOS, MIGRATIONS_DIR, SCHEMA_PATH, INSIGHTS_LOG_PATH
)
from enclothed.intake import add_garment
from enclothed.models import (
    ActAsIn, Garment, GarmentOut, LanguageIn, OptionsOut, Outfit, OutfitCreateIn, OutfitGarment, OutfitLikedIn, OutfitOut,
    OutfitSuggestIn, PreferencesImproveIn, PreferencesIn, PreferencesOut, ProfileOut, SetOut, UsageAllOut, UsageCall,
    User, UserOut, InsightsIn, InsightsOut
)
from enclothed.insights import answer_question
from enclothed.llm import UnusableResponse, improve_preferences
from enclothed.outfit import generate_outfits
from enclothed.usage import log_failed_call, read_calls

load_dotenv()

CurrentUser = Annotated[User, Depends(current_user)]
SignedInUser = Annotated[User, Depends(signed_in_user)]
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts: create the DB if it's new, apply any pending migrations."""
    db.init_db(DB_PATH, SCHEMA_PATH, MIGRATIONS_DIR)
    yield


app = FastAPI(title="enclothed", lifespan=lifespan)


class RevalidatedStaticFiles(StaticFiles):
    """Page files the browser must re-check before reusing, so updates show up on a normal refresh."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", RevalidatedStaticFiles(directory=PUBLIC_DIR), name="static")  # the page's CSS


def _anthropic_client() -> anthropic.Anthropic:
    """The API client, or a 503 explaining why the AI features are unavailable."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="No ANTHROPIC_API_KEY is set in .env, so AI features are off.")
    return anthropic.Anthropic()


def _require_demo_tokens(user: User) -> None:
    """Stop AI calls from the demo once today's limit is spent. Real wardrobes have no limit here."""
    if user.is_demo and demo.tokens_used(_usage_logs(), user.id) >= DEMO_DAILY_TOKEN_LIMIT:
        raise HTTPException(status_code=429, detail="The demo has used up today's AI allowance. It resets overnight.")


def _llm_failed(error: anthropic.APIError) -> HTTPException:
    logger.exception("LLM call failed")
    return HTTPException(status_code=502, detail=f"The AI service failed: {error.message}. Nothing was saved; try again.")


def _blank_to_none(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


# --- garments -----------------------
@app.get("/api/garments")
def list_garments(user: CurrentUser) -> list[GarmentOut]:
    return responses.list_garments(DB_PATH, user.id)


@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int, user: CurrentUser) -> GarmentOut:
    garment = responses.get_garment(DB_PATH, user.id, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment


@app.post("/api/garments", status_code=201)
def add_garment_from_photos(
    user: CurrentUser,
    photos_in: list[UploadFile] = File(alias="photos"),
    prompt_message: str | None = Form(None),
    notes: str | None = Form(None),
) -> GarmentOut:
    """Tag a new garment from uploaded photos (front, back, labels...) and save it."""
    if not 1 <= len(photos_in) <= UPLOAD_MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"Send between 1 and {UPLOAD_MAX_PHOTOS} photos.")
    _require_demo_tokens(user)
    client = _anthropic_client()
    saved_preferences = db.select_preferences(DB_PATH, user.id)

    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=INTAKE_DIR, prefix="upload-", ignore_cleanup_errors=True) as tmp:
        tmp_dir = Path(tmp)
        paths = []
        for index, upload in enumerate(photos_in):
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
            paths.append(str(photo))

        try:
            garment_id = add_garment(user.id, paths, DB_PATH, GARMENTS_DIR, INTAKE_DIR, TAGGING_LOG_PATH, client, False,
                                     _blank_to_none(prompt_message), _blank_to_none(notes), user.language,
                                     saved_preferences[0] if saved_preferences else None)
        except anthropic.APIError as error:
            raise _llm_failed(error)

    return responses.get_garment(DB_PATH, user.id, garment_id)


EDITABLE_FIELDS = set(Garment.model_fields) - {"id", "date_added", "set_id", "user_id"}

@app.patch("/api/garments/{garment_id}")
def edit_garment(garment_id: int, changes: dict[str, Any], user: CurrentUser) -> GarmentOut:
    garment = db.select_garment(DB_PATH, user.id, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")

    not_editable = changes.keys() - EDITABLE_FIELDS
    if not_editable:
        raise HTTPException(status_code=422, detail=f"Can't edit: {sorted(not_editable)}")

    try:
        edited = Garment.model_validate({**garment.model_dump(), **changes})
    except ValidationError as error:
        raise RequestValidationError(error.errors(include_url=False, include_input=False))

    db.update_garment(DB_PATH, user.id, edited)
    return responses.to_garment_out(edited)


# --- outfits -------------------------
@app.get("/api/outfits")
def list_outfits(user: CurrentUser) -> list[OutfitOut]:
    return responses.list_outfits(DB_PATH, user.id)


@app.get("/api/outfits/{outfit_id}")
def get_outfit(outfit_id: int, user: CurrentUser) -> OutfitOut:
    outfit = responses.get_outfit(DB_PATH, user.id, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return outfit


@app.post("/api/outfits/suggestions")
def suggest_outfits(body: OutfitSuggestIn, user: CurrentUser) -> list[OutfitOut]:
    """Ask the LLM for outfits built around the anchors and details; returns only the new, valid ones."""
    details = _blank_to_none(body.details)
    anchors = list(dict.fromkeys(body.anchors))
    if not anchors and not details:
        raise HTTPException(status_code=422, detail="Add at least one piece or some details.")

    wardrobe = {g.id: g for g in db.select_owned_garments(DB_PATH, user.id)}
    unknown = [i for i in anchors if i not in wardrobe]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Garment(s) not found: {unknown}")

    _require_demo_tokens(user)
    client = _anthropic_client()
    try:
        saved = db.select_preferences(DB_PATH, user.id)
        _, new_ids = generate_outfits(DB_PATH, user.id, wardrobe, anchors or None, OUTFIT_LOG_PATH, client,
                                      details or "everyday wear", False, preferences=saved[0] if saved else None,
                                      language=user.language)
    except anthropic.APIError as error:
        raise _llm_failed(error)
    return responses.get_outfits(DB_PATH, user.id, new_ids)


@app.post("/api/outfits", status_code=201)
def create_outfit(body: OutfitCreateIn, user: CurrentUser) -> OutfitOut:
    """Save an outfit the user put together themselves, without the LLM."""
    ids = [g.garment_id for g in body.garments]
    if len(set(ids)) < len(ids):
        raise HTTPException(status_code=422, detail="The same garment is in the outfit twice.")
    known = {g.id for g in db.select_owned_garments(DB_PATH, user.id)}
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
    [outfit_id] = db.insert_outfits(DB_PATH, user.id, [outfit], None, _blank_to_none(body.details) or MANUAL_OUTFIT_REQUEST, timestamp)
    return responses.get_outfit(DB_PATH, user.id, outfit_id)


@app.patch("/api/outfits/{outfit_id}")
def edit_outfit_liked(outfit_id: int, body: OutfitLikedIn, user: CurrentUser) -> OutfitOut:
    if not db.set_outfit_liked(DB_PATH, user.id, outfit_id, body.liked):
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return responses.get_outfit(DB_PATH, user.id, outfit_id)


# --- preferences ---------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/api/preferences")
def get_preferences(user: CurrentUser) -> PreferencesOut:
    saved = db.select_preferences(DB_PATH, user.id)
    return PreferencesOut(text=saved[0], updated_at=saved[1]) if saved else PreferencesOut()


@app.put("/api/preferences")
def put_preferences(body: PreferencesIn, user: CurrentUser) -> PreferencesOut:
    """Save the user's style preferences (sent with every outfit request). Empty text clears them."""
    db.save_preferences(DB_PATH, user.id, _blank_to_none(body.text), _now())
    return get_preferences(user)


@app.post("/api/preferences/improve")
def improve_preferences_text(body: PreferencesImproveIn, user: CurrentUser) -> PreferencesIn:
    """Ask the LLM to rewrite the text into a clearer brief. Returns the rewrite; saves nothing."""
    _require_demo_tokens(user)
    client = _anthropic_client()
    try:
        text, usage = improve_preferences(client, body.text)
    except anthropic.APIError as error:
        raise _llm_failed(error)
    except UnusableResponse as error:
        log_failed_call(PREFERENCES_LOG_PATH, user.id, error.usage, str(error))
        raise
    with PREFERENCES_LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"timestamp": _now(), "user_id": user.id, "usage": usage.model_dump(), "input": body.text, "output": text}, ensure_ascii=False) + "\n")
    return PreferencesIn(text=text)


# --- insights ------------------------
@app.post("/api/insights")
def ask_insights(body: InsightsIn, user: CurrentUser) -> InsightsOut:
    """Answer a question about this wardrobe. The browser keeps the conversation and sends it as history."""
    _require_demo_tokens(user)
    client = _anthropic_client()
    saved = db.select_preferences(DB_PATH, user.id)
    history = [message.model_dump() for message in body.history]
    try:
        result = answer_question(client, DB_PATH, user.id, body.question, history, user.language,
                                 saved[0] if saved else None, INSIGHTS_LOG_PATH)
    except anthropic.APIError as error:
        raise _llm_failed(error)
    except UnusableResponse:
        logger.exception("Insights gave no usable answer")
        raise HTTPException(status_code=502, detail="I couldn't work that out. Try asking it a different way.")
    return InsightsOut(answer=result.answer, queries=result.queries)


# --- sets ----------------------------
@app.get("/api/sets")
def list_sets(user: CurrentUser) -> list[SetOut]:
    return responses.list_sets(DB_PATH, user.id)


# --- options -------------------------
@app.get("/api/options")
def get_options(user: CurrentUser) -> OptionsOut:
    return responses.get_options(user.language)


# --- profile -------------------------
@app.get("/api/profile")
def get_profile(user: CurrentUser, me: SignedInUser) -> ProfileOut:
    """Whose wardrobe is showing, and what the page should offer the person looking at it."""
    demo_user = db.select_demo_user(DB_PATH)
    return ProfileOut(name=user.username, language=user.language, is_admin=me.is_admin,
                      signed_in_as=me.username if me.id != user.id else None,
                      is_demo=user.is_demo,
                      demo_user_id=demo_user.id if demo_user and demo_user.demo_reset_at else None)


@app.put("/api/language", status_code=204)
def put_language(body: LanguageIn, user: CurrentUser, me: SignedInUser) -> None:
    """Set the language of this wardrobe's fixed terms and of what the LLM writes for it from now on.

    In the shared demo this is your own setting, since the demo uses each visitor's language.
    """
    db.set_language(DB_PATH, me.id if user.is_demo else user.id, body.language)


# --- usage ---------------------------
DateParam = Annotated[datetime | None, Query()]
FromParam = Annotated[datetime | None, Query(alias="from")]


def _usage_logs() -> dict[str, Path]:
    return {"tagging": TAGGING_LOG_PATH, "outfits": OUTFIT_LOG_PATH, "style": PREFERENCES_LOG_PATH, "insights": INSIGHTS_LOG_PATH}


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
    return [UserOut(id=user.id, username=user.username) for user in db.select_all_users(DB_PATH)]


@app.put("/api/act-as", status_code=204)
def act_as(body: ActAsIn, me: SignedInUser, response: Response) -> None:
    """Switch wardrobes. Anyone can open the shared demo; only an admin can open someone else's.
    No user id, or your own, goes back to yours."""
    if body.user_id is None or body.user_id == me.id:
        response.delete_cookie(ACT_AS_COOKIE)
        return
    target = db.select_user(DB_PATH, body.user_id)
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


def _require_garment(user: User, garment_id: int) -> None:
    if db.select_garment(DB_PATH, user.id, garment_id) is None:
        raise HTTPException(status_code=404, detail="Photo not found")


@app.get("/photos/{garment_id}/{filename}", include_in_schema=False)
def get_photo(garment_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_garment(user, garment_id)
    return _photo_response(photos.get_photo(garment_id, filename))


@app.get("/thumbs/{garment_id}/{filename}", include_in_schema=False)
def get_thumbnail(garment_id: int, filename: str, user: CurrentUser) -> FileResponse:
    _require_garment(user, garment_id)
    return _photo_response(photos.get_thumbnail(garment_id, filename))


# --- front end -----------------------
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
