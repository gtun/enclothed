import sqlite3
from datetime import date
from pathlib import Path
from enclothed.models import DEFAULT_LANGUAGE, Garment, Language, Outfit, User, WeighOut, WeighVerdict
from contextlib import closing
import json
import logging

logger = logging.getLogger(__name__)

DB_DEFAULT_FIELDS = {"id", "date_added", "user_id"}
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

        if is_fresh:
            conn.executescript(sql)
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
def _garment_to_db_dict(garment: Garment) -> dict:
    garment_dict = garment.model_dump(mode="json", exclude=DB_DEFAULT_FIELDS)
    return {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
        for key, value in garment_dict.items()}


def insert_garment(db_path:Path, user_id: int, garment:Garment) -> int:
    garment_dict = {**_garment_to_db_dict(garment), "user_id": user_id}
    columns = ", ".join(garment_dict)
    placeholders = ", ".join(f":{name}" for name in garment_dict)
    with closing(_connect(db_path)) as conn:
        with conn:
            row_cursor = conn.execute(f"INSERT INTO garments ({columns}) VALUES ({placeholders})", garment_dict)
            return row_cursor.lastrowid


def update_garment(db_path: Path, user_id: int, garment: Garment) -> None:
    garment_dict = _garment_to_db_dict(garment)
    columns = ", ".join(f"{name} = :{name}" for name in garment_dict)
    garment_dict["id"] = garment.id
    garment_dict["user_id"] = user_id

    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute(f"UPDATE garments SET {columns} WHERE id = :id AND user_id = :user_id", garment_dict)


def set_mended_on(db_path: Path, user_id: int, garment_id: int, day: date) -> None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE garments SET mended_on = ? WHERE id = ? AND user_id = ?", (day.isoformat(), garment_id, user_id))


def select_garment(db_path: Path, user_id: int, garment_id: int) -> Garment | None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            garment_record = conn.execute(
                "SELECT * from garments where id = :id AND user_id = :user_id",
                {"id": garment_id, "user_id": user_id},
            ).fetchone()
            if garment_record:
                return _row_to_garment(garment_record)
            logger.debug("Garment ID %s not found", garment_id)
            return None #record with garment_id not found

def select_all_garments(db_path: Path, user_id: int) -> list[Garment]:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * from garments WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
            return [_row_to_garment(row) for row in rows]


def select_owned_garments(db_path: Path, user_id: int) -> list[Garment]:
    """Garments the user has now: not disowned, and not a candidate they're only weighing."""
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * from garments WHERE user_id = ? AND disowned_on IS NULL AND weighed_on IS NULL ORDER BY id", (user_id,)
            ).fetchall()
            return [_row_to_garment(row) for row in rows]


def _row_to_garment(row:sqlite3.Row) -> Garment:
    garment_dict = dict(row)
    for key in DB_JSON_COLUMNS:
        garment_dict[key] = json.loads(garment_dict[key]) if garment_dict[key] is not None else None
    return Garment.model_validate(garment_dict)


# --- weigh defs (#2) -------------
def insert_weigh(db_path: Path, user_id: int, garment_id: int, verdict: WeighVerdict, weighed_at: str) -> None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO weighs (garment_id, user_id, weighed_at, verdict) VALUES (?, ?, ?, ?)",
                         (garment_id, user_id, weighed_at, verdict.model_dump_json()))


def _row_to_weigh(row: sqlite3.Row) -> WeighOut:
    return WeighOut(garment_id=row["garment_id"], weighed_at=row["weighed_at"], verdict=WeighVerdict.model_validate_json(row["verdict"]))


def select_weighs(db_path: Path, user_id: int) -> list[WeighOut]:
    """Verdicts for garments still being weighed, newest first. Bought ones are left out."""
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT w.garment_id, w.weighed_at, w.verdict FROM weighs w JOIN garments g ON g.id = w.garment_id "
            "WHERE w.user_id = ? AND g.weighed_on IS NOT NULL ORDER BY w.weighed_at DESC, w.garment_id DESC", (user_id,)
        ).fetchall()
        return [_row_to_weigh(row) for row in rows]


def select_weigh(db_path: Path, user_id: int, garment_id: int) -> WeighOut | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT garment_id, weighed_at, verdict FROM weighs WHERE garment_id = ? AND user_id = ?",
                           (garment_id, user_id)).fetchone()
        return _row_to_weigh(row) if row else None


def buy_candidate(db_path: Path, user_id: int, garment_id: int) -> bool:
    """Make a weighed garment owned. False if it isn't this user's candidate."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute("UPDATE garments SET weighed_on = NULL WHERE id = ? AND user_id = ? AND weighed_on IS NOT NULL",
                                  (garment_id, user_id))
            return cursor.rowcount == 1


def delete_candidate(db_path: Path, user_id: int, garment_id: int) -> bool:
    """Delete a weighed garment, its verdict, and the outfits suggested with it. Refuses anything
    owned or disowned, so this can never delete a real wardrobe piece. False if there's nothing to delete."""
    with closing(_connect(db_path)) as conn:
        with conn:
            row = conn.execute("SELECT 1 FROM garments WHERE id = ? AND user_id = ? AND weighed_on IS NOT NULL",
                               (garment_id, user_id)).fetchone()
            if row is None:
                return False
            # Children before parents: foreign keys are on, so an outfit can't go while rows still point at it.
            outfit_ids = [(r[0],) for r in conn.execute("SELECT outfit_id FROM outfit_garments WHERE garment_id = ?", (garment_id,))]
            conn.executemany("DELETE FROM wears WHERE outfit_id = ?", outfit_ids)
            conn.executemany("DELETE FROM outfit_garments WHERE outfit_id = ?", outfit_ids)
            conn.executemany("DELETE FROM outfits WHERE id = ?", outfit_ids)
            conn.execute("DELETE FROM weighs WHERE garment_id = ?", (garment_id,))
            conn.execute("DELETE FROM garments WHERE id = ?", (garment_id,))
            return True


# --- outfit defs -------------
def insert_outfits(db_path: Path, user_id: int, valid_outfits: list[Outfit], anchors: list[int] | None, prompt_message: str, timestamp: str, source: str = "ai") -> list[int]:
    anchor_ids = set(anchors or [])
    new_ids: list[int] = []

    with closing(_connect(db_path)) as conn:
        with conn:
            for outfit in valid_outfits:
                cursor = conn.execute(
                    "INSERT INTO outfits (user_id, timestamp, prompt_message, aesthetic, explanation, missing, risk_tier, source) "
                    "VALUES (:user_id, :timestamp, :prompt_message, :aesthetic, :explanation, :missing, :risk_tier, :source)",
                    {
                        "user_id": user_id,
                        "timestamp": timestamp,
                        "prompt_message": prompt_message,
                        "aesthetic": outfit.aesthetic,
                        "explanation": outfit.explanation,
                        "missing": outfit.missing,
                        "risk_tier": outfit.risk_tier,
                        "source": source,
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
    "SELECT o.id, o.timestamp, o.prompt_message, o.aesthetic, o.explanation, o.missing, o.liked, o.risk_tier, o.source, "
    "(SELECT COUNT(*) FROM wears AS w WHERE w.outfit_id = o.id) AS wear_count, "
    "(SELECT MAX(w.date) FROM wears AS w WHERE w.outfit_id = o.id) AS last_worn, "
    "(SELECT json_group_array(json_object('id', w.id, 'date', w.date, 'notes', w.notes)) "
    " FROM (SELECT * FROM wears WHERE outfit_id = o.id ORDER BY date DESC, id DESC) AS w) AS wears, "
    "json_group_array(json_object("
    "'garment_id', og.garment_id, "
    "'styling_advice', og.styling_advice, "
    "'is_anchor', og.is_anchor"
    ")) FILTER (WHERE og.garment_id IS NOT NULL) AS garments "
    "FROM outfits AS o "
    "LEFT JOIN outfit_garments AS og ON og.outfit_id = o.id "
)

def _row_to_outfit(row: sqlite3.Row) -> dict:
    outfit = dict(row)
    outfit["garments"] = json.loads(outfit["garments"])
    outfit["wears"] = json.loads(outfit["wears"])
    return outfit

def select_outfit(db_path: Path, user_id: int, outfit_id: int) -> dict | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            OUTFIT_SELECT + "WHERE o.id = :id AND o.user_id = :user_id GROUP BY o.id",
            {"id": outfit_id, "user_id": user_id},
        ).fetchone()

    if row is None:
        logger.debug("Outfit ID %s not found", outfit_id)
        return None
    return _row_to_outfit(row)

def select_all_outfits(db_path: Path, user_id: int) -> list[dict]:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            OUTFIT_SELECT + "WHERE o.user_id = ? GROUP BY o.id ORDER BY o.id", (user_id,)
        ).fetchall()
    return [_row_to_outfit(row) for row in rows]


def insert_wear(db_path: Path, user_id: int, outfit_id: int, day: date, notes: str | None = None) -> int | None:
    """Log one wear of the user's outfit. Returns the new wear's ID, or None if the outfit isn't theirs."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO wears (outfit_id, date, notes) SELECT id, :date, :notes FROM outfits WHERE id = :id AND user_id = :user_id",
                {"id": outfit_id, "user_id": user_id, "date": day.isoformat(), "notes": notes},
            )
    if cursor.rowcount == 0:
        logger.debug("Outfit ID %s not found", outfit_id)
        return None
    return cursor.lastrowid


def delete_wear(db_path: Path, user_id: int, outfit_id: int, wear_id: int) -> bool:
    """Remove a wear logged by mistake. False if it isn't a wear of this user's outfit."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "DELETE FROM wears WHERE id = :wear_id AND outfit_id = :id AND outfit_id IN (SELECT id FROM outfits WHERE user_id = :user_id)",
                {"wear_id": wear_id, "id": outfit_id, "user_id": user_id},
            )
    return cursor.rowcount == 1


def set_outfit_liked(db_path: Path, user_id: int, outfit_id: int, liked: bool | None) -> bool:
    if liked not in (None, 0, 1):
        raise ValueError(f"liked must be None, 0, or 1; got {liked!r}")

    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE outfits SET liked = :liked WHERE id = :id AND user_id = :user_id",
                {"id": outfit_id, "user_id": user_id, "liked": liked},
            )
    if cursor.rowcount == 0:
        logger.debug("Outfit ID %s not found", outfit_id)
        return False
    return True


# --- set defs ----------------
def insert_set(db_path: Path, user_id: int, garment_ids: list[int], set_name: str | None) -> int:
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO sets (user_id, name) VALUES (:user_id, :name)",
                {"user_id": user_id, "name": set_name}
            )
            set_id = cursor.lastrowid

            cursor = conn.executemany(
                "UPDATE garments SET set_id = ? WHERE id = ? AND set_id IS NULL AND user_id = ?",
                [(set_id, garment_id, user_id) for garment_id in garment_ids],
            )
            if cursor.rowcount != len(garment_ids):
                raise ValueError(
                    f"Expected to add {len(garment_ids)} garments to a set, updated {cursor.rowcount}. "
                    f"Some of {sorted(garment_ids)} don't exist or already belong to a set."
                )

    return set_id


def select_all_sets(db_path, user_id: int) -> dict[int, str | None]:
    with closing(_connect(db_path)) as conn:
        with conn:
            return dict(conn.execute("SELECT id, name FROM sets WHERE user_id = ? ORDER BY id", (user_id,)).fetchall())


# --- preferences -------------
def select_preferences(db_path: Path, user_id: int) -> tuple[str, str] | None:
    """The saved (text, updated_at), or None when nothing is saved."""
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT style_notes, style_updated_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return (row[0], row[1]) if row and row[0] else None

def save_preferences(db_path: Path, user_id: int, text: str | None, timestamp: str) -> None:
    """Save the preferences text; empty or None removes it."""
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET style_notes = ?, style_updated_at = ? WHERE id = ?",
                (text or None, timestamp if text else None, user_id),
            )


# --- users -------------
def _row_to_user(row: sqlite3.Row) -> User:
    return User.model_validate(dict(row))

def select_user_by_username(db_path: Path, username: str) -> User | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE username = :username",
            { "username" : username }
        ).fetchone()

        if row is None:
            logger.debug("Username %s not found", username)
            return None
        return _row_to_user(row)

def select_user_by_email(db_path: Path, email: str) -> User | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(:email)",
            { "email" : email }
        ).fetchone()

        if row is None:
            logger.debug("Email %s not found", email)
            return None
        return _row_to_user(row)

def select_user(db_path: Path, user_id: int) -> User | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE id = :id", {"id": user_id}).fetchone()
    return _row_to_user(row) if row else None

def select_all_users(db_path: Path) -> list[User]:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_row_to_user(row) for row in rows]

def insert_user(db_path: Path, username: str, email: str, is_admin: bool = False, language: Language = DEFAULT_LANGUAGE) -> int:
    """Add a user. Emails are stored lowercase, so UNIQUE also catches a repeat in another case."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, is_admin, language) VALUES (?, ?, ?, ?)",
                (username, email.lower(), int(is_admin), language),
            )
    return cursor.lastrowid

def set_language(db_path: Path, user_id: int, language: Language) -> None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))

# --- the demo user -----------
def select_demo_user(db_path: Path) -> User | None:
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE is_demo = 1").fetchone()
    return _row_to_user(row) if row else None

def insert_demo_user(db_path: Path, username: str) -> int:
    """The demo has no email, so nobody can sign in as it. People reach it by switching to it."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute("INSERT INTO users (username, is_demo) VALUES (?, 1)", (username,))
    return cursor.lastrowid

def claim_demo_reset(db_path: Path, user_id: int, cutoff: str, timestamp: str) -> bool:
    """Mark the demo as reset unless it already has been since cutoff. True if this call claimed it."""
    with closing(_connect(db_path)) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE users SET demo_reset_at = ? "
                "WHERE id = ? AND is_demo = 1 AND (demo_reset_at IS NULL OR demo_reset_at < ?)",
                (timestamp, user_id, cutoff),
            )
    return cursor.rowcount == 1

def clear_demo_reset(db_path: Path, user_id: int) -> None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE users SET demo_reset_at = NULL WHERE id = ? AND is_demo = 1", (user_id,))

def delete_demo_wardrobe(db_path: Path, user_id: int, keep: set[int]) -> list[int]:
    """Delete the demo's outfits, sets, and every garment not in keep, and return the deleted
    garment ids. Refuses any real user."""
    with closing(_connect(db_path)) as conn:
        with conn:
            row = conn.execute("SELECT is_demo FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None or row[0] != 1:
                raise ValueError(f"User {user_id} isn't the demo user, so their wardrobe can't be deleted")
            all_ids = [r[0] for r in conn.execute("SELECT id FROM garments WHERE user_id = ?", (user_id,))]
            garment_ids = [i for i in all_ids if i not in keep]
            outfits = "(SELECT id FROM outfits WHERE user_id = ?)"
            conn.execute(f"DELETE FROM wears WHERE outfit_id IN {outfits}", (user_id,))
            conn.execute(f"DELETE FROM outfit_garments WHERE outfit_id IN {outfits}", (user_id,))
            conn.execute("DELETE FROM outfits WHERE user_id = ?", (user_id,))
            conn.execute("UPDATE garments SET set_id = NULL WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM weighs WHERE user_id = ?", (user_id,))
            conn.executemany("DELETE FROM garments WHERE id = ? AND user_id = ?", [(i, user_id) for i in garment_ids])
            conn.execute("DELETE FROM sets WHERE user_id = ?", (user_id,))
    return garment_ids


def update_user(db_path: Path, user_id: int, username: str, email: str | None) -> None:
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET username = ?, email = ? WHERE id = ?",
                (username, email.lower() if email else None, user_id),
            )
