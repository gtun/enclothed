import sqlite3
from pathlib import Path
from wardrobe_ai.models import Garment
from contextlib import closing
import json

DB_DEFAULT_FIELDS = {"id","wear_count","last_worn","date_added"}

def init_db(db_path:Path, schema_path:Path) -> None:
    print("generating Garments table...")
    sql = schema_path.read_text()
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executescript(sql)
    
    return

def insert_garment(db_path:Path, garment:Garment) -> int:
    print("inserting garment:")
    
    garment_dict = garment.model_dump(mode="json", exclude=DB_DEFAULT_FIELDS)
    garment_dict = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list,dict)) else value
        for key, value in garment_dict.items()}
    
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            row_cursor = conn.execute("INSERT INTO garments (category, subcategory, primary_color, secondary_colors, accent_colors, formality, materials, warmth, pattern, country_of_origin, style_tags, notes, styling_notes, label_text, fit, sheen, brand) VALUES (:category, :subcategory, :primary_color, :secondary_colors, :accent_colors, :formality, :materials, :warmth, :pattern, :country_of_origin, :style_tags, :notes, :styling_notes, :label_text, :fit, :sheen, :brand)",
                garment_dict
            )
            return row_cursor.lastrowid

def select_garment() -> Garment:
    
    pass