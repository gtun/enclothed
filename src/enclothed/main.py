from enclothed import config
from enclothed import db
from enclothed import demo
from enclothed import mend
import argparse
import sqlite3
from dotenv import load_dotenv
from anthropic import Anthropic
from enclothed.intake import add_garment, is_url
from enclothed.outfit import get_outfits
from pathlib import Path
import logging
from typing import get_args
from enclothed.models import DEFAULT_LANGUAGE, LIST_FILTER_CHOICES, Language, RiskTier, Silhouette
from enclothed.cli_display import format_list, format_new_garment, format_outfit_result

logger = logging.getLogger(__name__)

def owner_language() -> Language:
    """The language of the user the CLI works as, so its LLM calls match the web app's."""
    owner = db.select_user(config.DB_PATH, config.DEFAULT_USER_ID)
    return owner.language if owner else DEFAULT_LANGUAGE

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
    outfit_parser.add_argument("-n", "--count", type=int, default=config.DEFAULT_OUTFIT_COUNT, choices=range(config.MIN_OUTFIT_COUNT, config.MAX_OUTFIT_COUNT + 1), metavar=f"{{{config.MIN_OUTFIT_COUNT}-{config.MAX_OUTFIT_COUNT}}}", help=f"How many outfits to suggest (default {config.DEFAULT_OUTFIT_COUNT})")
    outfit_parser.add_argument("-r", "--riskiness", choices=get_args(RiskTier), help="Suggest every outfit at this tier. Without it, the outfits are spread across safe, stretch and bold")
    outfit_parser.add_argument("-s", "--silhouette", choices=get_args(Silhouette), help="Make every outfit form this letter silhouette (I, H, A, Y, O or X). Without it, any shape")
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

    adduser_parser = subparsers.add_parser("adduser", parents=[common], help="Add a person who can sign in")
    adduser_parser.add_argument("username")
    adduser_parser.add_argument("email", help="The email they sign in to Cloudflare Access with")
    adduser_parser.add_argument("--admin", action="store_true", help="Let them switch between wardrobes")
    adduser_parser.add_argument("-l", "--language", choices=get_args(Language), default=DEFAULT_LANGUAGE)

    edituser_parser = subparsers.add_parser("edituser", parents=[common], help="Change a user's username, email or language")
    edituser_parser.add_argument("id", type=int)
    edituser_parser.add_argument("-u", "--username")
    edituser_parser.add_argument("-e", "--email")
    edituser_parser.add_argument("-l", "--language", choices=get_args(Language))

    mend_parser = subparsers.add_parser("mend", parents=[common], help="Fill in blank fields with AI, without review. Never overwrites a value")
    mend_parser.add_argument("ids", type=int, nargs="*", help="Only these garments. Default: every garment with blank fields")
    mend_parser.add_argument("-l", "--limit", type=int, help="Stop after this many garments, to test a small batch first")
    mend_parser.add_argument("-r", "--retry", action="store_true", help="Include garments mend has already tried")
    mend_parser.add_argument("-u", "--user-id", type=int, default=config.DEFAULT_USER_ID, help="Whose wardrobe to mend")

    subparsers.add_parser("users", parents=[common], help="List everyone who can sign in")

    demo_parser = subparsers.add_parser("demo-seed", parents=[common], help="Rebuild the shared demo wardrobe from a sample of yours")
    demo_parser.add_argument("--per-category", type=int, default=config.DEMO_PER_CATEGORY, help="At least this many garments per category, when you have them")
    demo_parser.add_argument("--outfits", type=int, default=config.DEMO_MAX_OUTFITS, help="At most this many outfits, liked ones first")

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
        saved_preferences = db.select_preferences(config.DB_PATH, config.DEFAULT_USER_ID)
        new_garment_id = add_garment(config.DEFAULT_USER_ID, args.photos, config.DB_PATH, config.GARMENTS_DIR, config.INTAKE_DIR, config.TAGGING_LOG_PATH, client, args.test, args.prompt_message, args.notes, owner_language(),
                                     saved_preferences[0] if saved_preferences else None)

        new_garment = db.select_garment(config.DB_PATH, config.DEFAULT_USER_ID, new_garment_id)
        if new_garment is None:
            raise RuntimeError(f"Garment {new_garment_id} not found after insert")

        print(format_new_garment(new_garment))

    # --- list ------------------
    elif args.command == "list":
        wardrobe = db.select_owned_garments(config.DB_PATH, config.DEFAULT_USER_ID)
        if not wardrobe:
            print("Sorry, you have no items in your wardrobe to list. Go shopping and add something with: enclothed add <photos>")
            return 0

        wardrobe_sets = db.select_all_sets(config.DB_PATH, config.DEFAULT_USER_ID)

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
        wardrobe = {g.id: g for g in db.select_owned_garments(config.DB_PATH, config.DEFAULT_USER_ID)}
        if args.anchors:
            missing = [i for i in args.anchors if i not in wardrobe]
            if missing:
                outfit_parser.error(f"Invalid garment ID{'s' if len(missing) > 1 else ''}: {missing}")
        user_prompt = args.prompt_message or "everyday wear"
        client = None if args.test else Anthropic()
        saved_preferences = db.select_preferences(config.DB_PATH, config.DEFAULT_USER_ID)
        result = get_outfits(config.DB_PATH, config.DEFAULT_USER_ID, wardrobe, args.anchors, config.OUTFIT_LOG_PATH, client, user_prompt, args.test, args.cache,
                             preferences=saved_preferences[0] if saved_preferences else None, language=owner_language(),
                             count=args.count, riskiness=args.riskiness, silhouette=args.silhouette)
        print(format_outfit_result(result, wardrobe))

    # --- set ----------------------
    elif args.command == "set":
        garment_ids = set(args.garment_ids)
        if len(garment_ids) < 2:
            set_parser.error("At least two unique garments required to create a set. Add them with -g/--garment <ID>")
        wardrobe = {g.id: g for g in db.select_owned_garments(config.DB_PATH, config.DEFAULT_USER_ID)}
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
        db.insert_set(config.DB_PATH, config.DEFAULT_USER_ID, valid_garments, args.name)

    # --- users --------------------
    elif args.command == "adduser":
        try:
            new_id = db.insert_user(config.DB_PATH, args.username, args.email, args.admin, args.language)
        except sqlite3.IntegrityError:
            adduser_parser.error(f"That username or email is already in use: {args.username}, {args.email}")
        print(f"Added {args.username} as user {new_id}")

    elif args.command == "edituser":
        user = db.select_user(config.DB_PATH, args.id)
        if user is None:
            edituser_parser.error(f"User {args.id} not found")
        try:
            db.update_user(config.DB_PATH, args.id, args.username or user.username, args.email or user.email)
        except sqlite3.IntegrityError:
            edituser_parser.error("That username or email is already in use")
        if args.language:
            db.set_language(config.DB_PATH, args.id, args.language)
        print(f"Updated user {args.id}")

    elif args.command == "mend":
        load_dotenv()
        user = db.select_user(config.DB_PATH, args.user_id)
        if user is None:
            mend_parser.error(f"No user {args.user_id}")
        saved_preferences = db.select_preferences(config.DB_PATH, user.id)
        failures = mend.mend_all(config.DB_PATH, config.TAGGING_LOG_PATH, user.id, Anthropic(), args.ids, args.limit, args.retry, user.language,
                                 saved_preferences[0] if saved_preferences else None)
        return 1 if failures else 0

    elif args.command == "users":
        for user in db.select_all_users(config.DB_PATH):
            print(f"{user.id}  {user.username}  {user.email or '(no email)'}  {user.language}{'  admin' if user.is_admin else ''}")

    elif args.command == "demo-seed":
        template = demo.seed(config.DB_PATH, config.DEFAULT_USER_ID, args.per_category, args.outfits)
        print(f"Demo wardrobe ready: {len(template['garments'])} garments, {len(template['outfits'])} outfits, {len(template['sets'])} sets")

    return 0

def init_dirs():
    for directory in (config.GARMENTS_DIR, config.INTAKE_DIR):
        directory.mkdir(parents=True, exist_ok=True)

def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("enclothed").setLevel(logging.DEBUG if verbose else logging.INFO)
