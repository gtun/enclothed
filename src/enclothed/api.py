from fastapi import FastAPI, HTTPException
from enclothed import db
from enclothed.config import DB_PATH
from enclothed.models import Garment

app = FastAPI(title="enclothed")

@app.get("/api/garments")
def list_garments() -> list[Garment]:
    return db.select_all_garments(DB_PATH)

@app.get("/api/garments/{garment_id}")
def get_garment(garment_id: int) -> Garment:
    garment = db.select_garment(DB_PATH, garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail=f"Garment {garment_id} not found")
    return garment
