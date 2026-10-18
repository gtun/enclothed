from wardrobe_ai import config
from wardrobe_ai import db
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic
from wardrobe_ai.intake import add_garment
import logging

logger = logging.getLogger(__name__)

def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="show debug output")

    parser = argparse.ArgumentParser(prog="wardrobe-ai")
    subparsers = parser.add_subparsers(dest="command", required=False)

    add_parser = subparsers.add_parser("add", parents=[common], help="Tag and save a new garment")
    add_parser.add_argument("photos", type=str, nargs="*")
    add_parser.add_argument("-t","--test", action="store_true", help="Suppress actual LLM calls")
    add_parser.add_argument("-p", "--prompt-message", type=str, help="Details about garment to fine-tune the LLM tagging")
    add_parser.add_argument("-n", "--notes", type=str, help="Add personal notes about this garment")
    
    outfit_parser = subparsers.add_parser("outfit", parents=[common], help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("prompt", type=str)

    args = parser.parse_args()

    if not args.command:
        parser.error("Missing command")

    configure_logging(args.verbose)

    init_dirs()
    db.init_db(config.DB_PATH, config.SCHEMA_PATH)
    
    if args.command == "add":
        
        load_dotenv()
        if args.test:
            logger.info("Running in testing mode. No requests to LLMs will be made")
        if not args.photos and not args.test:
            add_parser.error("At least one photo URL or filepath needed")
        client = None if args.test else Anthropic()
        logger.info('Adding your garment now. Please wait...')
        add_garment(args.photos, config.DB_PATH, config.GARMENTS_DIR, config.INTAKE_DIR, config.TAGGING_LOG_PATH, client, args.test, args.prompt_message, args.notes)
    
    return 0

def init_dirs():
    for directory in (config.GARMENTS_DIR, config.INTAKE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        
def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("wardrobe_ai").setLevel(logging.DEBUG if verbose else logging.INFO)