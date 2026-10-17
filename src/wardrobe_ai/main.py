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
    add_parser.add_argument("photos", type=str, nargs="*")
    add_parser.add_argument("-t","--test", action="store_true", help="Suppress actual LLM calls")
    
    outfit_parser = subparsers.add_parser("outfit", help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("prompt", type=str)
    
    
    args = parser.parse_args()
    
    if args.test:
        print("Running in testing mode. No requests to LLMs will be made")
    
    init_dirs()
    db.init_db(config.DB_PATH, config.SCHEMA_PATH)
    
    if not args.command:
        parser.error("Missing command")
    
    load_dotenv()
    client = Anthropic()
    
    if args.command == "add":
        if not args.photos and not args.test:
            add_parser.error("At least one photo URL or filepath needed")
        add_garment(args.photos, config.DB_PATH, config.GARMENTS_DIR, config.INTAKE_DIR, client, args.test)
    
    #response = llm.call_llm(client)
    #print(response.content)
    
    return 0

def init_dirs():
    for directory in (config.GARMENTS_DIR, config.INTAKE_DIR):
        directory.mkdir(parents=True, exist_ok=True)