-- mimic (#5): a photographed look, broken down into its pieces, and the outfits that recreate it from the wardrobe.
-- pieces is JSON: what the tagging call saw, one record per piece, numbered from 1 in the order stored.
CREATE TABLE looks (
    id INTEGER PRIMARY KEY NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    note TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    silhouette TEXT CHECK (silhouette IN ('I', 'H', 'A', 'Y', 'O', 'X')),
    pieces TEXT NOT NULL
);

-- The look an outfit recreates. NULL for every other outfit, and for one whose look was deleted: it stays an outfit.
ALTER TABLE outfits ADD COLUMN look_id INTEGER REFERENCES looks(id);

-- Which owned garment stands in for each piece of the look in a recreation, and how close it is.
-- garment_id is NULL when nothing owned does the piece's job.
CREATE TABLE look_matches (
    outfit_id INTEGER NOT NULL REFERENCES outfits(id),
    piece INTEGER NOT NULL,
    garment_id INTEGER REFERENCES garments(id),
    closeness TEXT NOT NULL CHECK (closeness IN ('exact', 'close', 'loose', 'none')),
    note TEXT,
    PRIMARY KEY (outfit_id, piece)
);
