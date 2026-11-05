import sqlite3
from enclothed.config import INSIGHTS_VALUE_SIZE_LIMIT
from contextlib import closing
from pathlib import Path

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

WHERE_FILTERS = {
    "garments" : " WHERE user_id = :user_id",
    "sets" : " WHERE user_id = :user_id",
    "outfits" : " WHERE user_id = :user_id",
    "outfit_garments" : " WHERE outfit_id IN (SELECT id FROM outfits WHERE user_id = :user_id)",
    "wears" : " WHERE outfit_id IN (SELECT id FROM outfits WHERE user_id = :user_id)",
}

def build_snapshot(db_path: Path, user_id: int) -> sqlite3.Connection:
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn_src:
        with sqlite3.connect(":memory:") as conn_tmp:


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

    lock_snapshot(conn_tmp)
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
