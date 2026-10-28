import sqlite3
from pathlib import Path
from enclothed.models import Garment, Outfit
from contextlib import closing
import json
import logging

logger = logging.getLogger(__name__)

DB_DEFAULT_FIELDS = {"id","date_added"}
DB_JSON_COLUMNS = [
    "secondary_colors",
    "accent_colors",
    "materials",
    "style_tags"
]

def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _migration_number(path: Path) -> int:
    return int(path.name.split("_")[0])

def init_db(db_path: Path, schema_path: Path, migrations_dir: Path) -> None:
    migrations = sorted(migrations_dir.glob("*.sql"))
    latest = _migration_number(migrations[-1]) if migrations else 0
    sql = schema_path.read_text()
    with closing(_connect(db_path)) as conn:
        is_fresh = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'garments'"
        ).fetchone() is None

        conn.executescript(sql)

        if is_fresh:
            conn.execute(f"PRAGMA user_version = {latest}")
            return

        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for path in migrations:
            number = _migration_number(path)
            if number <= current:
                continue
            logger.info("Applying migration %s", path.name)
            try:
                conn.executescript(
                    f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {number};\nCOMMIT;"
                )
            except sqlite3.Error:
                conn.rollback()
                raise

    return

def insert_garment(db_path:Path, garment:Garment) -> int:
    garment_dict = garment.model_dump(mode="json", exclude=DB_DEFAULT_FIELDS)
    garment_dict = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list,dict)) else value
        for key, value in garment_dict.items()}

    with closing(_connect(db_path)) as conn:
        with conn:
            row_cursor = conn.execute("INSERT INTO garments (category, subcategory, primary_color, secondary_colors, accent_colors, formality, materials, warmth, pattern, country_of_origin, style_tags, notes, styling_notes, label_text, fit, sheen, brand) VALUES (:category, :subcategory, :primary_color, :secondary_colors, :accent_colors, :formality, :materials, :warmth, :pattern, :country_of_origin, :style_tags, :notes, :styling_notes, :label_text, :fit, :sheen, :brand)",
                garment_dict
            )
            return row_cursor.lastrowid

def select_garment(db_path: Path, garment_id: int) -> Garment | None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            garment_record = conn.execute("SELECT * from garments where id = :id", {"id":garment_id}).fetchone()
            if garment_record:
                return _row_to_garment(garment_record)
            logger.debug("Garment ID %s not found", garment_id)
            return None #record with garment_id not found

def select_all_garments(db_path: Path) -> list[Garment]:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * from garments ORDER BY id").fetchall()
            return [_row_to_garment(row) for row in rows]

def _row_to_garment(row:sqlite3.Row) -> Garment:
    garment_dict = dict(row)
    for key in DB_JSON_COLUMNS:
        garment_dict[key] = json.loads(garment_dict[key]) if garment_dict[key] is not None else None
    return Garment.model_validate(garment_dict)

def insert_outfits(db_path: Path, valid_outfits: list[Outfit], anchors: list[int] | None, prompt_message: str, timestamp: str) -> list[int]:
    anchor_ids = set(anchors or [])
    new_ids: list[int] = []

    with closing(_connect(db_path)) as conn:
        with conn:
            for outfit in valid_outfits:
                cursor = conn.execute(
                    "INSERT INTO outfits (timestamp, prompt_message, aesthetic, explanation, missing) "
                    "VALUES (:timestamp, :prompt_message, :aesthetic, :explanation, :missing)",
                    {
                        "timestamp": timestamp,
                        "prompt_message": prompt_message,
                        "aesthetic": outfit.aesthetic,
                        "explanation": outfit.explanation,
                        "missing": outfit.missing,
                    },
                )
                outfit_id = cursor.lastrowid

                for garment in outfit.garments:
                    conn.execute(
                        "INSERT INTO outfit_garments (outfit_id, garment_id, styling_advice, is_anchor) "
                        "VALUES (:outfit_id, :garment_id, :styling_advice, :is_anchor)",
                        {
                            "outfit_id": outfit_id,
                            "garment_id": garment.garment_id,
                            "styling_advice": garment.styling_advice,
                            "is_anchor": int(garment.garment_id in anchor_ids),
                        },
                    )

                new_ids.append(outfit_id)

    logger.debug("Inserted outfits %s", new_ids)
    return new_ids
