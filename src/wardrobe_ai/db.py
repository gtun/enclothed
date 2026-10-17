import sqlite3
from pathlib import Path
from wardrobe_ai.models import Garment
from contextlib import closing

def init_db(db_path:Path, schema_path:Path) -> None:
    print("generating Garments table...")
    sql = schema_path.read_text()
    with closing(sqlite3.connect(db_path)) as con:
        with con:
            con.executescript(sql)
    
    return

def insert_garment(garment:Garment) -> int:
    
    pass

def select_garment() -> Garment:
    
    pass