from wardrobe_ai import config
from wardrobe_ai import db
from wardrobe_ai import llm
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic
from wardrobe_ai.intake import add_garment

def main() -> int:
    parser = argparse.ArgumentParser(prog="wardrobe-ai")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    add_parser = subparsers.add_parser("add", help="Tag and save a new garment")
    add_parser.add_argument("photos", type=str, nargs="+")
    
    outfit_parser = subparsers.add_parser("outfit", help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("prompt", type=str)
    
    args = parser.parse_args()
    
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    db.init_db(config.DB_PATH, config.SCHEMA_PATH)
    
    load_dotenv()
    client = Anthropic()
    
    if not args.command:
        parser.error("Missing command")
    
    if args.command == "add":
        print("add invoked")
        add_garment(args.photos)
    
    #response = llm.call_llm(client)
    #print(response.content)
    
    return 0