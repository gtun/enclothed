from enclothed import config
from enclothed import db
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic
from enclothed.intake import add_garment, is_url
from enclothed.outfit import get_outfits
from pathlib import Path
import logging
from enclothed.models import LIST_FILTER_CHOICES
from enclothed.cli_display import format_list, format_new_garment, format_outfit_result

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
        action="extend",
        nargs="+",
        dest="anchors",
        metavar="ID",
        help="One or more garment IDs to build an outfit around (e.g. -w 3 4)",
    )
    outfit_parser.add_argument("--no-cache", action="store_false", dest="cache", help="Don't cache the wardrobe. By default it's cached for 5 minutes, so repeat calls use far fewer tokens (the first costs ~25% more)")

    set_parser = subparsers.add_parser("set", parents=[common], help="Tag multiple garments as part of the same set")
    set_parser.add_argument("-n", "--name", help="Name the set")
    set_parser.add_argument("-g", "--garment-ids",
        dest="garment_ids",
        required=True,
        metavar="ID",
        type=int,
        action="extend",
        nargs="+",
    )

    args = parser.parse_args()

    if not args.command:
        parser.error("Missing command")

    configure_logging(args.verbose)

    init_dirs()
    db.init_db(config.DB_PATH, config.SCHEMA_PATH, config.MIGRATIONS_DIR)

    # --- add ------------------
    if args.command == "add":
        load_dotenv()
        if args.test:
            logger.info("Running in testing mode. No requests to LLMs will be made")
        if not args.photos and not args.test:
            add_parser.error("At least one photo URL or filepath needed")

        invalid_photo_paths = []
        for photo in args.photos:
            if not is_url(photo) and not Path(photo).is_file():
                invalid_photo_paths.append(photo)
        if invalid_photo_paths:
            add_parser.error(f"Nonexistent filepath(s): {invalid_photo_paths}")

        client = None if args.test else Anthropic()
        logger.info('Adding your garment now. Please wait...')
        new_garment_id = add_garment(args.photos, config.DB_PATH, config.GARMENTS_DIR, config.INTAKE_DIR, config.TAGGING_LOG_PATH, client, args.test, args.prompt_message, args.notes)

        new_garment = db.select_garment(config.DB_PATH, new_garment_id)
        if new_garment is None:
            raise RuntimeError(f"Garment {new_garment_id} not found after insert")

        print(format_new_garment(new_garment))

    # --- list ------------------
    elif args.command == "list":
        wardrobe = db.select_all_garments(config.DB_PATH)
        if not wardrobe:
            print("Sorry, you have no items in your wardrobe to list. Go shopping and add something with: enclothed add <photos>")
            return 0

        wardrobe_sets = db.select_all_sets(config.DB_PATH)

        if args.category:
            wardrobe = [garment for garment in wardrobe if garment.category in args.category or garment.subcategory in args.category]

        if not wardrobe:
            print(f"No matches found for '{', '.join(args.category)}'")
        else:
            print(format_list(wardrobe, wardrobe_sets))

    # --- outfit ------------------
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
        result = get_outfits(config.DB_PATH, wardrobe, args.anchors, config.OUTFIT_LOG_PATH, client, user_prompt, args.test, args.cache)
        print(format_outfit_result(result, wardrobe))

    # --- set ----------------------
    elif args.command == "set":
        garment_ids = set(args.garment_ids)
        if len(garment_ids) < 2:
            set_parser.error("At least two unique garments required to create a set. Add them with -g/--garment <ID>")
        wardrobe = {g.id: g for g in db.select_all_garments(config.DB_PATH)}
        valid_garments = garment_ids & wardrobe.keys()
        if len(valid_garments) < len(garment_ids):
            set_parser.error(f"Garment IDs {', '.join(map(str, garment_ids - valid_garments))} not found")
        garments_in_sets = []
        for garment_id in valid_garments:
            if wardrobe[garment_id].set_id is not None:
                garments_in_sets.append(garment_id)
        if garments_in_sets:
            set_parser.error(f"{', '.join(map(str, garments_in_sets))} already belongs to a set")
        logger.info("Creating set %s with garment IDs %s...", repr(args.name) if args.name else "(no name)", ", ".join(map(str, sorted(garment_ids))))
        db.insert_set(config.DB_PATH, valid_garments, args.name)

    return 0

def init_dirs():
    for directory in (config.GARMENTS_DIR, config.INTAKE_DIR):
        directory.mkdir(parents=True, exist_ok=True)

def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("enclothed").setLevel(logging.DEBUG if verbose else logging.INFO)
