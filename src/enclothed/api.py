from fastapi import FastAPI, HTTPException
from enclothed import db
from enclothed.config import DB_PATH
from enclothed.models import Garment, OutfitOut
from fastapi.staticfiles import StaticFiles
from enclothed.config import GARMENTS_DIR

app = FastAPI(title="enclothed")

GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=GARMENTS_DIR), name="photos")

@app.get("/api/garments")
def list_garments() -> list[Garment]:
    return db.select_all_garments(DB_PATH)

@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int) -> Garment:
    garment = db.select_garment(DB_PATH, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment

@app.get("/api/outfits")
def list_outfits() -> list[OutfitOut]:
    return db.select_all_outfits(DB_PATH)

@app.get("/api/outfits/{outfit_id}")
def get_outfit(outfit_id: int) -> OutfitOut:
    outfit = db.select_outfit(DB_PATH, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return outfit
