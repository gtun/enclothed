from wardrobe_ai import models
from pathlib import Path
from urllib.parse import urlparse

def add_garment(image_paths:list[str]):
    # print(models.Garment.model_json_schema())
    for image_path in image_paths:
        scheme = urlparse(image_path).scheme
        print(f"{image_path} is scheme: {scheme}")
        
    #temporary hardcode
    