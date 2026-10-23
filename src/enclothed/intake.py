from enclothed.models import Garment, MaterialPart, Fiber, PhotoTag, TaggingResult, TokenUsage
from pathlib import Path
import mimetypes
import requests
import shutil
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from enclothed.db import insert_garment
from anthropic import Anthropic
from enclothed.llm import tag_garment
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

TEST_GARMENT = Garment(
    category="outerwear",
    subcategory="blouson",
    primary_color="black",
    secondary_colors=["white"],
    accent_colors=["gunmetal"],
    formality=2,
    materials=[
        MaterialPart(part="shell", fibers=[Fiber(fiber="cotton", percent=100)]),
        MaterialPart(part="front lining", fibers=[
            Fiber(fiber="polyester", percent=78),
            Fiber(fiber="cotton", percent=22),
        ]),
    ],
    warmth=2,
    pattern="solid",
    country_of_origin="Japan",
    style_tags=["corduroy", "double-breasted", "raglan sleeve", "cropped",
                "workwear", "japanese designer", "collaboration"],
    notes="Test garment. Bought secondhand at 2nd Street; runs slightly short in the body.",
    styling_notes=(
        "A collarless, double-breasted take on the trucker jacket: chest yoke, welt "
        "pockets, and snap-adjustable waist tabs from workwear, with a wrap-style front "
        "and raglan sleeves that soften it toward a kimono line. Cropped at the hip, so it "
        "suits higher-rise and wide or relaxed trousers. The faded charcoal corduroy "
        "bridges registers: it holds up against rugged workwear (double-knee or carpenter "
        "pants, boots) and dresses up over a knit or band-collar shirt with pleated "
        "trousers. With no collar, the neckline frames whatever is underneath, so mock "
        "necks, crewneck knits, and plain tees work best; a collared shirt can look busy. "
        "Matte texture pairs well with smooth fabrics for contrast."
    ),
    label_text=(
        "nonnative UNDERCOVER / UN-J0501 / UC1F9202 / SIZE: M / OUTER LAYER COTTON 100% / "
        "FRONT LINING POLYESTER 78% COTTON 22% / DO NOT TUMBLE DRY / made in Japan || "
        "表地 綿 100% / 前裏 ポリエステル 78% 綿 22% / 日本製"
    ),
    fit="regular",
    sheen="matte",
    brand="nonnative x UNDERCOVER",
)

def add_garment(image_paths:list[str], garment_db_path:Path, garments_path:Path, intake_dir:Path, logging_path:Path, client:Anthropic | None, is_test:bool, prompt_message:str | None = None, notes:str | None = None) -> int:
    run_dir = intake_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir()

    logger.info("Staging your photos...")
    staged_paths = []
    for image_path in image_paths:
        scheme = urlparse(image_path).scheme
        if scheme in ("http","https"):
            staged_paths.append(download_photo(image_path, run_dir, len(staged_paths)))
        else:
            dest = run_dir / f"{len(staged_paths):02d}_{Path(image_path).name}"
            shutil.copy2(image_path, dest)
            staged_paths.append(dest)

    if is_test:
        wrapper, usage = TaggingResult(garment=TEST_GARMENT, photos=[]), None
    else:
        logger.info(f"Sending {len(staged_paths)} photos for analysis...")
        start = time.perf_counter()
        wrapper, usage = tag_garment(client, staged_paths, prompt_message)
        elapsed = time.perf_counter() - start
        logger.info(f"Tagged in {elapsed:.1f}s: {wrapper.garment.name}")

    if notes:
        wrapper.garment.notes = notes

    new_garment_id = insert_garment(garment_db_path, wrapper.garment)

    log_tagging(logging_path, new_garment_id, wrapper, usage, prompt_message)
    file_photos(staged_paths, wrapper.photos, garments_path / str(new_garment_id))
    logger.debug(f'Photos filed to {garments_path / str(new_garment_id)}')

    run_dir.rmdir()

    return new_garment_id

def download_photo(url: str, dest_dir: Path, index: int) -> Path:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type","").split(";")[0].strip()
    if not content_type.startswith("image/"):
        raise ValueError(f"{url} is not an image (Content-Type: {content_type or 'missing'})")

    ext = mimetypes.guess_extension(content_type) or ".img"
    dest = dest_dir / f"url_{index}{ext}"
    dest.write_bytes(response.content)
    return dest

def file_photos(staged: list[Path], tagged: list[PhotoTag], garment_dir: Path) -> None:
    filename_mapping = zip(staged, photo_filenames(staged, tagged), strict=True)
    garment_dir.mkdir(parents=True, exist_ok=True)
    for src, name in filename_mapping:
        shutil.move(src, garment_dir / name)

def photo_filenames(staged: list[Path], tagged: list[PhotoTag]) -> list[str]:
    if sorted(tag.index for tag in tagged) != list(range(len(staged))):
        logger.warning(
            f"Photo roles didn't match the {len(staged)} staged photos "
            f"(got indexes {sorted(tag.index for tag in tagged)}); keeping original filenames"
        )
        return [p.name for p in staged]

    ordered = sorted(tagged, key=lambda tag: tag.index)

    filenames = []
    role_count = defaultdict(int)
    for tag in ordered:
        filenames.append(f"{tag.role}_{role_count[tag.role]:02d}{staged[tag.index].suffix}")
        role_count[tag.role] += 1

    return filenames

def log_tagging(log_path: Path, garment_id: int, result: TaggingResult, usage: TokenUsage | None, prompt_message: str | None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "garment_id": garment_id,
        "usage": usage.model_dump() if usage else None,
        "result": result.model_dump(mode="json"),
        "prompt_message": prompt_message,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
