from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from enclothed import responses
from enclothed.config import DB_PATH, GARMENTS_DIR
from enclothed.models import GarmentOut, OutfitOut

app = FastAPI(title="enclothed")

GARMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=GARMENTS_DIR), name="photos")

@app.get("/api/garments")
def list_garments() -> list[GarmentOut]:
    return responses.list_garments(DB_PATH)

@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int) -> GarmentOut:
    garment = responses.get_garment(DB_PATH, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment

@app.get("/api/outfits")
def list_outfits() -> list[OutfitOut]:
    return responses.list_outfits(DB_PATH)

@app.get("/api/outfits/{outfit_id}")
def get_outfit(outfit_id: int) -> OutfitOut:
    outfit = responses.get_outfit(DB_PATH, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail=f"Outfit {outfit_id} not found")
    return outfit
