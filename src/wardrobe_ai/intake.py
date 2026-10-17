from wardrobe_ai.models import Garment, MaterialPart, Fiber
from pathlib import Path
from urllib.parse import urlparse
from wardrobe_ai.db import insert_garment

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

def add_garment(image_paths:list[str], garment_data_path:str):
    # print(Garment.model_json_schema())
    for image_path in image_paths:
        scheme = urlparse(image_path).scheme
        print(f"{image_path} is scheme: {scheme or 'file path'}")
        
    #temporary hardcode
    new_garment = TEST_GARMENT
    new_garment_id = insert_garment(garment_data_path, TEST_GARMENT)
    print(new_garment_id)