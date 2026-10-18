from wardrobe_ai.models import Garment, MaterialPart, Fiber, PhotoTag, TaggingResult
from pathlib import Path
from datetime import datetime
import mimetypes
import requests
import shutil
from urllib.parse import urlparse
from wardrobe_ai.db import insert_garment
from anthropic import Anthropic
from wardrobe_ai.llm import tag_garment

TEST_GARMENT = Garment(
    category="outerwear",
    subcategory="trucker jacket",
    primary_color="charcoal",
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
    style_tags=["corduroy", "collarless", "double-breasted", "raglan sleeve",
                "cropped", "workwear", "japanese designer", "collaboration"],
    notes=None,
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
    fit=None,
    sheen="matte",
    brand="nonnative x UNDERCOVER",
)

def add_garment(image_paths:list[str], garment_db_path:Path, garments_path:Path, intake_dir:Path, client:Anthropic, is_test:bool):
    run_dir = intake_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir()
    
    staged_paths = []
    for image_path in image_paths:
        scheme = urlparse(image_path).scheme
        if scheme in ("http","https"):
            staged_paths.append(download_photo(image_path, run_dir, len(staged_paths)))
        else:
            dest = run_dir / Path(image_path).name
            shutil.copy2(image_path, dest)
            staged_paths.append(dest)
    
    wrapper = TaggingResult(garment=TEST_GARMENT, photos=[]) if is_test else tag_garment(client, staged_paths)
    
    new_garment_id = insert_garment(garment_db_path, wrapper.garment)
    file_photos(staged_paths, wrapper.photos, garments_path / str(new_garment_id))
    
    print(f"new garment ID {new_garment_id} added")

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
    print("staged:")
    print(staged)
    print("===============")
    print("tagged")
    print(tagged)
    print("===============")
    print(f"save to: {garment_dir}")
    pass