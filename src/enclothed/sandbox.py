import sqlite3
from enclothed.config import INSIGHTS_VALUE_SIZE_LIMIT, INSIGHTS_SIZE_FUSE_LIMIT, INSIGHTS_TIME_LIMIT
from contextlib import closing
from enclothed.models import Color, QueryResult, SUBCATEGORIES, color_traits, layer_for
import time
import json
from pathlib import Path
from typing import get_args

INSIGHTS_SCHEMA = {
    "garments": {
        "id" : "INTEGER PRIMARY KEY",
        "category" : "TEXT",
        "subcategory" : "TEXT",
        "primary_color" : "TEXT",
        "secondary_colors" : "TEXT",
        "accent_colors" : "TEXT",
        "formality" : "INTEGER",
        "materials" : "TEXT",
        "warmth" : "INTEGER",
        "pattern" : "TEXT",
        "country_of_origin" : "TEXT",
        "style_tags": "TEXT",
        "styling_notes" : "TEXT",
        "fit" : "TEXT",
        "sheen" : "TEXT",
        "fabric_type" : "TEXT",
        "shape" : "TEXT",
        "hem" : "TEXT",
        "fabric_weight" : "TEXT",
        "sleeve" : "TEXT",
        "statement" : "TEXT",
        "brand" : "TEXT",
        "date_added" : "TEXT NOT NULL",
        "set_id" : "INTEGER",
        "disowned_on" : "TEXT",
    },
    "sets": {
        "id" : "INTEGER PRIMARY KEY",
        "name" : "TEXT",
    },
    "outfits": {
        "id" : "INTEGER PRIMARY KEY",
        "timestamp" : "TEXT",
        "prompt_message" : "TEXT",
        "aesthetic" : "TEXT",
        "explanation" : "TEXT",
        "missing" : "TEXT",
        "liked" : "INTEGER",
        "source" : "TEXT",
    },
    "outfit_garments": {
        "outfit_id" : "INTEGER",
        "garment_id" : "INTEGER",
        "styling_advice" : "TEXT",
        "is_anchor" : "INTEGER",
    },
    "wears": {
        "id" : "INTEGER PRIMARY KEY",
        "outfit_id" : "INTEGER",
        "date" : "TEXT",
    },
}

# Worked out in code rather than copied from anyone's data, so every snapshot gets the same rows.
LOOKUP_SCHEMA = {
    "colors": {
        "name" : "TEXT PRIMARY KEY",
        "family" : "TEXT",
        "temperature" : "TEXT",
        "lightness" : "TEXT",
        "saturation" : "TEXT",
    },
    "layers": {
        "subcategory" : "TEXT",
        "category" : "TEXT",
        "layer" : "TEXT",
    },
}


def lookup_rows() -> dict[str, list[tuple]]:
    colors = []
    for color in get_args(Color):
        traits = color_traits(color)
        colors.append((color, traits["family"], traits["temperature"], traits["lightness"], traits["saturation"]))

    layers = [
        (subcategory, category, layer_for(category, subcategory))
        for category, subcategories in SUBCATEGORIES.items()
        for subcategory in sorted(subcategories)
        if layer_for(category, subcategory)
    ]
    return {"colors": colors, "layers": layers}


# Candidates from weigh (weighed_on set) aren't the user's, so they and the outfits suggested with
# them stay out of the snapshot. Insights then can't count them by mistake, whatever SQL it writes.
_CANDIDATE_OUTFITS = ("SELECT og.outfit_id FROM outfit_garments og JOIN garments g ON g.id = og.garment_id "
                      "WHERE g.weighed_on IS NOT NULL")
_USER_OUTFITS = f"SELECT id FROM outfits WHERE user_id = :user_id AND id NOT IN ({_CANDIDATE_OUTFITS})"
WHERE_FILTERS = {
    "garments" : " WHERE user_id = :user_id AND weighed_on IS NULL",
    "sets" : " WHERE user_id = :user_id",
    "outfits" : f" WHERE id IN ({_USER_OUTFITS})",
    "outfit_garments" : f" WHERE outfit_id IN ({_USER_OUTFITS})",
    "wears" : f" WHERE outfit_id IN ({_USER_OUTFITS})",
}

def build_snapshot(db_path: Path, user_id: int) -> sqlite3.Connection:
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn_src:
        conn_tmp = sqlite3.connect(":memory:")
        try:
            with conn_tmp:
                for table, columns in INSIGHTS_SCHEMA.items():
                    tmp_columns = ",".join(columns)
                    src_rows = conn_src.execute(f"select {tmp_columns} FROM {table}{WHERE_FILTERS[table]}",
                        { "user_id" : user_id },
                    ).fetchall()

                    tmp_schema = [f"CREATE TABLE {table} ("]
                    tmp_schema.append(','.join([f"{column_name} {column_props}" for column_name, column_props in columns.items()]))
                    tmp_schema.append(");")
                    tmp_schema = "\n".join(tmp_schema)
                    conn_tmp.execute(tmp_schema)

                    ins_placeholder = ",".join("?" * len(columns))
                    conn_tmp.executemany(
                        f"INSERT INTO {table} VALUES ({ins_placeholder})",
                        src_rows
                    )

                for table, rows in lookup_rows().items():
                    columns = LOOKUP_SCHEMA[table]
                    definitions = ",".join(f"{column_name} {column_props}" for column_name, column_props in columns.items())
                    conn_tmp.execute(f"CREATE TABLE {table} ({definitions});")
                    ins_placeholder = ",".join("?" * len(columns))
                    conn_tmp.executemany(f"INSERT INTO {table} VALUES ({ins_placeholder})", rows)

            lock_snapshot(conn_tmp)

        except BaseException:
            conn_tmp.close()
            raise

        return conn_tmp


def lock_snapshot(conn: sqlite3.Connection) -> None:
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, INSIGHTS_VALUE_SIZE_LIMIT)
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(insights_authorizer)


def insights_authorizer(action_code, arg1, arg2, db_name, trigger):
    # List of allowed read-only actions
    allowed_actions = {
        sqlite3.SQLITE_SELECT,   # Basic SELECT statement execution
        sqlite3.SQLITE_READ,     # Reading a specific table/column
        sqlite3.SQLITE_FUNCTION,  # Running a built-in SQL function
        sqlite3.SQLITE_RECURSIVE,
    }

    return sqlite3.SQLITE_OK if action_code in allowed_actions else sqlite3.SQLITE_DENY


def run_select(conn: sqlite3.Connection, sql: str) -> QueryResult:
    deadline = time.monotonic() + INSIGHTS_TIME_LIMIT
    conn.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
    try:
        cursor = conn.execute(sql)
        if cursor.description is None:
            return QueryResult(error="That didn't run a query. Send one SELECT statement.")

        column_names = [column[0] for column in cursor.description]

        table_size = 0
        rows = []
        for row in cursor:
            table_size += len(json.dumps(row, default=str, ensure_ascii=False))
            rows.append(row)
            if table_size > INSIGHTS_SIZE_FUSE_LIMIT:
                return QueryResult(error=f"Result passed the {INSIGHTS_SIZE_FUSE_LIMIT} character limit after {len(rows)} rows. Select fewer columns, or use COUNT or GROUP BY.")

        return QueryResult(columns=column_names, rows=rows)

    except sqlite3.Error as e:
        return QueryResult(error=f"An SQLite error occurred: {e}")
    finally:
        conn.set_progress_handler(None, 0)


def insights_schema_text() -> str:
    lines = []
    for table, columns in {**INSIGHTS_SCHEMA, **LOOKUP_SCHEMA}.items():
        lines.append(f"{table}: " + ", ".join([f"{column_name} {column_props}" for column_name, column_props in columns.items()]))
    return "\n".join(lines)
