-- weigh (#2): a garment photographed while shopping is saved as a candidate, not as owned.
-- weighed_on is the day it was weighed; NULL for garments you own (and for disowned ones).
-- "I bought it" clears it, which makes the garment owned without re-tagging its photos.
ALTER TABLE garments ADD COLUMN weighed_on TEXT;

-- One verdict per candidate: the yes/no checks and recommendation, as JSON. Kept after buying, as history.
CREATE TABLE weighs (
    garment_id INTEGER PRIMARY KEY NOT NULL REFERENCES garments(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    weighed_at TEXT NOT NULL,
    verdict TEXT NOT NULL
);
