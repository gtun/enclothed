import sqlite3
from pathlib import Path
from enclothed.models import Garment, Outfit, OutfitOut, OutfitGarmentOut, GarmentOut
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


# --- garment defs ----------
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


# --- outfit defs -------------
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


OUTFIT_SELECT = (
    "SELECT o.id, o.timestamp, o.prompt_message, o.aesthetic, o.explanation, o.missing, o.liked, "
    "json_group_array(json_object("
    "'garment_id', og.garment_id, "
    "'styling_advice', og.styling_advice, "
    "'is_anchor', og.is_anchor"
    ")) FILTER (WHERE og.garment_id IS NOT NULL) AS garments "
    "FROM outfits AS o "
    "LEFT JOIN outfit_garments AS og ON og.outfit_id = o.id "
)

def _row_to_outfit(row: sqlite3.Row, wardrobe: dict[int, GarmentOut]) -> OutfitOut:
    outfit_dict = dict(row)
    outfit_dict["garments"] = [
        OutfitGarmentOut(
            garment=wardrobe[entry["garment_id"]],
            styling_advice=entry["styling_advice"],
            is_anchor=entry["is_anchor"],
        )
        for entry in json.loads(row["garments"])
    ]
    return OutfitOut(**outfit_dict)

def _wardrobe_by_id(db_path: Path) -> dict[int, GarmentOut]:
    return {garment.id: GarmentOut(**garment.model_dump()) for garment in select_all_garments(db_path)}

def select_outfit(db_path: Path, outfit_id: int) -> OutfitOut | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            OUTFIT_SELECT + "WHERE o.id = :id GROUP BY o.id",
            {"id": outfit_id},
        ).fetchone()

    if row is None:
        logger.debug("Outfit ID %s not found", outfit_id)
        return None
    return _row_to_outfit(row, _wardrobe_by_id(db_path))

def select_all_outfits(db_path: Path) -> list[OutfitOut]:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(OUTFIT_SELECT + "GROUP BY o.id ORDER BY o.id").fetchall()

    wardrobe = _wardrobe_by_id(db_path)
    return [_row_to_outfit(row, wardrobe) for row in rows]


# --- set defs ----------------
def insert_set(db_path: Path, garment_ids: list[int], set_name: str | None) -> int:
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO sets (name) VALUES (:name)",
                {"name": set_name,}
            )
            set_id = cursor.lastrowid

            cursor = conn.executemany(
                "UPDATE garments SET set_id = ? WHERE id = ? and set_id is null",
                [(set_id, garment_id) for garment_id in garment_ids],
            )
            if cursor.rowcount != len(garment_ids):
                raise ValueError(
                    f"Expected to add {len(garment_ids)} garments to a set, updated {cursor.rowcount}. "
                    f"Some of {sorted(garment_ids)} don't exist or already belong to a set."
                )

    return set_id


def select_all_sets(db_path) -> dict[int, str | None]:
    with closing(_connect(db_path)) as conn:
        with conn:
            return dict(conn.execute("SELECT id, name FROM sets").fetchall())
