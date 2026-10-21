import sqlite3
from pathlib import Path
from wardrobe_ai.models import Garment
from contextlib import closing
import json
import logging

logger = logging.getLogger(__name__)

DB_DEFAULT_FIELDS = {"id","wear_count","last_worn","date_added"}
DB_JSON_COLUMNS = [
    "secondary_colors",
    "accent_colors",
    "materials",
    "style_tags"
]

def init_db(db_path:Path, schema_path:Path) -> None:
    sql = schema_path.read_text()
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executescript(sql)

    return

def insert_garment(db_path:Path, garment:Garment) -> int:
    garment_dict = garment.model_dump(mode="json", exclude=DB_DEFAULT_FIELDS)
    garment_dict = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list,dict)) else value
        for key, value in garment_dict.items()}

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            row_cursor = conn.execute("INSERT INTO garments (category, subcategory, primary_color, secondary_colors, accent_colors, formality, materials, warmth, pattern, country_of_origin, style_tags, notes, styling_notes, label_text, fit, sheen, brand) VALUES (:category, :subcategory, :primary_color, :secondary_colors, :accent_colors, :formality, :materials, :warmth, :pattern, :country_of_origin, :style_tags, :notes, :styling_notes, :label_text, :fit, :sheen, :brand)",
                garment_dict
            )
            return row_cursor.lastrowid

def select_garment(db_path: Path, garment_id: int) -> Garment | None:
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            garment_record = conn.execute("SELECT * from garments where id = :id", {"id":garment_id}).fetchone()
            if garment_record:
                return _row_to_garment(garment_record)
            logger.debug("Garment ID %s not found", garment_id)
            return None #record with garment_id not found

def select_all_garments(db_path: Path) -> list[Garment]:
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * from garments ORDER BY id").fetchall()
            return [_row_to_garment(row) for row in rows]

def _row_to_garment(row:sqlite3.Row) -> Garment:
    garment_dict = dict(row)
    for key in DB_JSON_COLUMNS:
        garment_dict[key] = json.loads(garment_dict[key]) if garment_dict[key] is not None else None
    return Garment.model_validate(garment_dict)
