from wardrobe_ai.models import Garment, MaterialPart, Fiber
from pathlib import Path
from urllib.parse import urlparse

TEST_GARMENT = Garment(
    category="outerwear",
    subcategory="other",
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
                "trucker-style", "cropped", "japanese designer", "collaboration"],
    notes="Collarless double-breasted corduroy jacket with snap closures, trucker-style "
          "yoke and welt pockets, adjustable snap tabs at back hem. OZISM patch at front hem.",
    label_text="nonnative UNDERCOVER / UN-J0501 / UC1F9202 / SIZE: M / OUTER LAYER COTTON 100% / "
               "FRONT LINING POLYESTER 78% COTTON 22% / DO NOT TUMBLE DRY / made in Japan || "
               "表地 綿 100% / 前裏 ポリエステル 78% 綿 22% / 日本製",
    fit=None,
    sheen="matte",
    brand="nonnative x UNDERCOVER",
)

def add_garment(image_paths:list[str]):
    # print(Garment.model_json_schema())
    for image_path in image_paths:
        scheme = urlparse(image_path).scheme
        print(f"{image_path} is scheme: {scheme}")
        
    #temporary hardcode
    new_garment = TEST_GARMENT