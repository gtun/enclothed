from enclothed import config
from enclothed import db
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic
from enclothed.intake import add_garment
from enclothed.outfit import get_outfits
import logging
from enclothed.models import CATEGORY_ORDER, LIST_FILTER_CHOICES

logger = logging.getLogger(__name__)

def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="show debug output")

    parser = argparse.ArgumentParser(prog="enclothed")
    subparsers = parser.add_subparsers(dest="command", required=False)

    add_parser = subparsers.add_parser("add", parents=[common], help="Tag and save a new garment")
    add_parser.add_argument("photos", type=str, nargs="*")
    add_parser.add_argument("-t","--test", action="store_true", help="Suppress actual LLM calls")
    add_parser.add_argument("-p", "--prompt-message", help="Details about garment to fine-tune the LLM tagging")
    add_parser.add_argument("-n", "--notes", type=str, help="Add personal notes about this garment")

    list_parser = subparsers.add_parser("list", parents=[common], help="List all garments in your wardrobe")
    list_parser.add_argument(
        "-c", "--category",
        action="append",
        choices=LIST_FILTER_CHOICES,
        metavar="CATEGORY",
        help="List only these categories or subcategories (repeatable)",
    )

    outfit_parser = subparsers.add_parser("outfit", parents=[common], help="Ask AI for help with an outfit in natural language.")
    outfit_parser.add_argument("-t","--test", action="store_true", help="Suppress actual LLM calls")
    outfit_parser.add_argument("-p","--prompt-message", help="Details about what you are dressing up for")
    outfit_parser.add_argument(
        "-w","--with",
        type=int,
        action="append",
        dest="anchors",
        metavar="ID",
        help="Pass a garment ID to build an outfit around it (repeatable)",
    )

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
        new_garment_id = add_garment(args.photos, config.DB_PATH, config.GARMENTS_DIR, config.INTAKE_DIR, config.TAGGING_LOG_PATH, client, args.test, args.prompt_message, args.notes)
        print(f"new garment ID {new_garment_id} added")

    elif args.command == "list":
        garments = sorted(db.select_all_garments(config.DB_PATH), key=lambda garment: (CATEGORY_ORDER[garment.category], garment.subcategory, garment.id),)
        if args.category:
            garments = [garment for garment in garments if garment.category in args.category or garment.subcategory in args.category]

        for category in CATEGORY_ORDER:
            print(f"{category.upper()} {'=' * (45 - len(category))}")
            for garment in garments:
                if garment.category == category:
                    print(f"  {garment.id:>3}  {garment.name}")

    elif args.command == "outfit":
        load_dotenv()
        if not args.anchors and not args.prompt_message:
            outfit_parser.error("At least one of -p/--prompt-message or -w/--with required")
        wardrobe = {g.id: g for g in db.select_all_garments(config.DB_PATH)}
        if args.anchors:
            missing = [i for i in args.anchors if i not in wardrobe]
            if missing:
                outfit_parser.error(f"Invalid garment ID{'s' if len(missing) > 1 else ''}: {missing}")
        user_prompt = args.prompt_message or "everyday wear"
        client = None if args.test else Anthropic()
        result = get_outfits(wardrobe, args.anchors, config.OUTFIT_LOG_PATH, client, user_prompt, args.test)
        print(result.model_dump_json(indent=2))

    return 0

def init_dirs():
    for directory in (config.GARMENTS_DIR, config.INTAKE_DIR):
        directory.mkdir(parents=True, exist_ok=True)

def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("enclothed").setLevel(logging.DEBUG if verbose else logging.INFO)
