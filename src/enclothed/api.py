import getpass
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from enclothed import db, photos, responses
from enclothed.config import (
    DB_PATH, GARMENTS_DIR, INTAKE_DIR, MANUAL_OUTFIT_REQUEST, OUTFIT_LOG_PATH, PUBLIC_DIR,
    TAGGING_LOG_PATH, UPLOAD_MAX_BYTES, UPLOAD_MAX_PHOTOS,
)
from enclothed.intake import add_garment
from enclothed.models import (
    Garment, GarmentOut, OptionsOut, Outfit, OutfitCreateIn, OutfitGarment, OutfitLikedIn, OutfitOut,
    OutfitSuggestIn, ProfileOut, SetOut,
)
from enclothed.outfit import generate_outfits

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="enclothed")

GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=GARMENTS_DIR), name="photos")


def _anthropic_client() -> anthropic.Anthropic:
    """The API client, or a 503 explaining why the AI features are unavailable."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="No ANTHROPIC_API_KEY is set in .env, so AI features are off.")
    return anthropic.Anthropic()


def _llm_failed(error: anthropic.APIError) -> HTTPException:
    logger.exception("LLM call failed")
    return HTTPException(status_code=502, detail=f"The AI service failed: {error.message}. Nothing was saved; try again.")


def _blank_to_none(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


# --- garments -----------------------
@app.get("/api/garments")
def list_garments() -> list[GarmentOut]:
    return responses.list_garments(DB_PATH)


@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int) -> GarmentOut:
    garment = responses.get_garment(DB_PATH, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment


@app.post("/api/garments", status_code=201)
def add_garment_from_photos(
    photos_in: list[UploadFile] = File(alias="photos"),
    prompt_message: str | None = Form(None),
    notes: str | None = Form(None),
) -> GarmentOut:
    """Tag a new garment from uploaded photos (front, back, labels...) and save it."""
    if not 1 <= len(photos_in) <= UPLOAD_MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"Send between 1 and {UPLOAD_MAX_PHOTOS} photos.")
    client = _anthropic_client()

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
            garment_id = add_garment(paths, DB_PATH, GARMENTS_DIR, INTAKE_DIR, TAGGING_LOG_PATH, client, False,
                                     _blank_to_none(prompt_message), _blank_to_none(notes))
        except anthropic.APIError as error:
            raise _llm_failed(error)

    return responses.get_garment(DB_PATH, garment_id)


EDITABLE_FIELDS = set(Garment.model_fields) - {"id", "date_added", "set_id"}

@app.patch("/api/garments/{garment_id}")
def edit_garment(garment_id: int, changes: dict[str, Any]) -> GarmentOut:
    garment = db.select_garment(DB_PATH, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")

    not_editable = changes.keys() - EDITABLE_FIELDS
    if not_editable:
        raise HTTPException(status_code=422, detail=f"Can't edit: {sorted(not_editable)}")

    try:
        edited = Garment.model_validate({**garment.model_dump(), **changes})
    except ValidationError as error:
        raise RequestValidationError(error.errors(include_url=False, include_input=False))

    db.update_garment(DB_PATH, edited)
    return responses.to_garment_out(edited)


# --- outfits -------------------------
@app.get("/api/outfits")
def list_outfits() -> list[OutfitOut]:
    return responses.list_outfits(DB_PATH)


@app.get("/api/outfits/{outfit_id}")
def get_outfit(outfit_id: int) -> OutfitOut:
    outfit = responses.get_outfit(DB_PATH, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return outfit


@app.post("/api/outfits/suggestions")
def suggest_outfits(body: OutfitSuggestIn) -> list[OutfitOut]:
    """Ask the LLM for outfits built around the anchors and details; returns only the new, valid ones."""
    details = _blank_to_none(body.details)
    anchors = list(dict.fromkeys(body.anchors))
    if not anchors and not details:
        raise HTTPException(status_code=422, detail="Add at least one piece or some details.")

    wardrobe = {g.id: g for g in db.select_all_garments(DB_PATH)}
    unknown = [i for i in anchors if i not in wardrobe]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Garment(s) not found: {unknown}")

    client = _anthropic_client()
    try:
        _, new_ids = generate_outfits(DB_PATH, wardrobe, anchors or None, OUTFIT_LOG_PATH, client,
                                      details or "everyday wear", False)
    except anthropic.APIError as error:
        raise _llm_failed(error)
    return responses.get_outfits(DB_PATH, new_ids)


@app.post("/api/outfits", status_code=201)
def create_outfit(body: OutfitCreateIn) -> OutfitOut:
    """Save an outfit the user put together themselves, without the LLM."""
    ids = [g.garment_id for g in body.garments]
    if len(set(ids)) < len(ids):
        raise HTTPException(status_code=422, detail="The same garment is in the outfit twice.")
    known = {g.id for g in db.select_all_garments(DB_PATH)}
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
    [outfit_id] = db.insert_outfits(DB_PATH, [outfit], None, _blank_to_none(body.details) or MANUAL_OUTFIT_REQUEST, timestamp)
    return responses.get_outfit(DB_PATH, outfit_id)


@app.patch("/api/outfits/{outfit_id}")
def edit_outfit_liked(outfit_id: int, body: OutfitLikedIn) -> OutfitOut:
    if not db.set_outfit_liked(DB_PATH, outfit_id, body.liked):
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return responses.get_outfit(DB_PATH, outfit_id)


# --- sets ----------------------------
@app.get("/api/sets")
def list_sets() -> list[SetOut]:
    return responses.list_sets(DB_PATH)


# --- options -------------------------
@app.get("/api/options")
def get_options() -> OptionsOut:
    return responses.get_options()


# --- profile -------------------------
@app.get("/api/profile")
def get_profile() -> ProfileOut:
    """Display name for the page header: ENCLOTHED_USER_NAME, else the OS login name."""
    return ProfileOut(name=os.getenv("ENCLOTHED_USER_NAME") or getpass.getuser())


# --- thumbnails ----------------------
@app.get("/thumbs/{garment_id}/{filename}", include_in_schema=False)
def get_thumbnail(garment_id: int, filename: str) -> FileResponse:
    path = photos.get_thumbnail(garment_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, headers={"Cache-Control": "max-age=3600"})


# --- front end -----------------------
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")
