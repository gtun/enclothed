from wardrobe_ai import config
from wardrobe_ai import db
from wardrobe_ai import llm
from pathlib import Path
import argparse
import os
from dotenv import load_dotenv
from anthropic import Anthropic

def main() -> int:
    parser = argparse.ArgumentParser(prog="wardrobe-ai")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    add_parser = subparsers.add_parser("add", help="Tag and save a new garment")
    add_parser.add_argument("photos", type=str, nargs="+")
    
    outfit_parser = subparsers.add_parser("outfit", help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("prompt", type=str)
    
    args = parser.parse_args()
    
    
    db.init_db(config.DB_PATH, config.SCHEMA_PATH)
    
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    
    if not api_key:
        raise RuntimeError("LLM API key not set. Check your .env file.")
    
    response = llm.call_llm(client);
    print(response);
    
    return 0

def add_garment():
    pass