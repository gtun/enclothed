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
                garment_dict = dict(garment_record)
                for key in DB_JSON_COLUMNS:
                    garment_dict[key] = json.loads(garment_dict[key])
                return Garment.model_validate(garment_dict)
            logger.debug(f'Garment ID {garment_id} not found for select_garment()')
            return None #record with garment_id not found