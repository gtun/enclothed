from enclothed.config import GARMENTS_DIR
from enclothed.models import Photo, PhotoRole
from typing import get_args

ROLES = get_args(PhotoRole)   # ("front", "back", "detail", "label", "other")



def get_garment_photos(garment_id: int) -> list[Photo]:
    photos_dir = GARMENTS_DIR / str(garment_id)
    if not photos_dir.is_dir():
        return []
    photos = [p for p in photos_dir.iterdir() if p.is_file() and not p.name.startswith(".")]

    photo_list = []
    for p in photos:
        prefix = p.name.split("_")[0]
        role = prefix if prefix in ROLES else "other"
        photo_list.append(Photo(role=role, url=f"/photos/{garment_id}/{p.name}"))

    photo_list.sort(key=lambda photo: (ROLES.index(photo.role), photo.url))

    return photo_list
