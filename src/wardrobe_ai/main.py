from wardrobe_ai import config
from wardrobe_ai import db
from pathlib import Path
import argparse

def main() -> int:
    parser = argparse.ArgumentParser(prog="wardrobe-ai")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    add_parser = subparsers.add_parser("add", help="Tag and save a new garment")
    add_parser.add_argument("photos", type=str, nargs="+")
    
    outfit_parser = subparsers.add_parser("outfit", help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("prompt", type=str)
    
    args = parser.parse_args()
    
    db.init_db(config.DB_PATH, config.SCHEMA_PATH)
    
    
    
    return 0

def add_garment():
    pass