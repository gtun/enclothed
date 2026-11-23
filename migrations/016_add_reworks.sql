-- Rework (#74): an image model's edit of one of a garment's photos, such as "make it bright blue". The image is
-- data/reworks/<id>.jpg, apart from the garment's photos, so a preview is never mistaken for a real photo.
-- Deleting a garment deletes its reworks; the files go at the next start (reworks.remove_orphaned_files).
CREATE TABLE reworks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    garment_id INTEGER NOT NULL REFERENCES garments(id) ON DELETE CASCADE,
    instruction TEXT NOT NULL,
    source_photo TEXT NOT NULL,   -- the photo's file name in the garment's folder
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);
