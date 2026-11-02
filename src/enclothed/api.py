import getpass
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from enclothed import db, responses
from enclothed.config import DB_PATH, GARMENTS_DIR, PUBLIC_DIR
from enclothed.models import Garment, GarmentOut, OptionsOut, OutfitOut, OutfitLikedIn, ProfileOut, SetOut
from typing import Any
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

load_dotenv()

app = FastAPI(title="enclothed")

GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=GARMENTS_DIR), name="photos")


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


# --- front end -----------------------
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")
