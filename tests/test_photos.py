"""Thumbnails on a small server: a page can ask for dozens of new ones at once."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from enclothed import config, photos


def add_photo(garment_id, size=(100, 100)):
    folder = config.GARMENTS_DIR / str(garment_id)
    folder.mkdir(parents=True)
    Image.new("RGB", size, "navy").save(folder / "front_00.jpg")


def test_thumbnails_are_made_one_at_a_time(monkeypatch):
    real = photos._upright_rgb
    lock = threading.Lock()
    running, peak = [0], [0]

    def tracked(image):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(0.03)
        with lock:
            running[0] -= 1
        return real(image)

    monkeypatch.setattr(photos, "_upright_rgb", tracked)
    for garment_id in range(1, 13):
        add_photo(garment_id)
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda i: photos.get_thumbnail(i, "front_00.jpg"), range(1, 13)))

    assert peak[0] == 1
    assert all(path.suffix == ".jpg" and path.parent.parent.name == "thumbs" for path in results)


def test_many_requests_for_one_photo_make_one_thumbnail(monkeypatch):
    real = photos._upright_rgb
    calls = []

    def counted(image):
        calls.append(1)
        return real(image)

    monkeypatch.setattr(photos, "_upright_rgb", counted)
    add_photo(1)
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda _: photos.get_thumbnail(1, "front_00.jpg"), range(6)))
    assert len(calls) == 1


def test_a_large_jpeg_is_decoded_at_a_reduced_size(monkeypatch):
    real = photos._upright_rgb
    seen = {}

    def spy(image):
        seen["size"] = image.size
        return real(image)

    monkeypatch.setattr(photos, "_upright_rgb", spy)
    add_photo(1, (4000, 3000))
    thumb = photos.get_thumbnail(1, "front_00.jpg")
    assert max(seen["size"]) <= 2000
    with Image.open(thumb) as result:
        assert result.size == (600, 450)


def test_a_failed_thumbnail_doesnt_block_the_next():
    folder = config.GARMENTS_DIR / "1"
    folder.mkdir(parents=True)
    bad = folder / "front_00.jpg"
    bad.write_bytes(b"not an image")
    for _ in range(2):
        assert photos.get_thumbnail(1, "front_00.jpg") == bad


def test_big_or_unusual_photos_are_shrunk_before_sending(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MEND_MAX_PHOTO_BYTES", 10)
    big = tmp_path / "front_00.jpg"
    Image.new("RGB", (100, 100), "red").save(big)
    out = tmp_path / "out"
    out.mkdir()

    [ready] = photos.sendable_copies([big], out)

    assert ready.parent == out
    assert ready.suffix == ".jpg"


def test_small_photos_are_sent_as_they_are(tmp_path):
    small = tmp_path / "front_00.jpg"
    Image.new("RGB", (10, 10), "red").save(small)
    assert photos.sendable_copies([small], tmp_path) == [small]
