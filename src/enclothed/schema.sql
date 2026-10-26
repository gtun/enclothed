CREATE TABLE IF NOT EXISTS garments (
    id INTEGER PRIMARY KEY NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    primary_color TEXT NOT NULL,
    secondary_colors TEXT,
    accent_colors TEXT,
    formality INTEGER,
    materials TEXT,
    warmth INTEGER,
    pattern TEXT,
    country_of_origin TEXT,
    style_tags TEXT,
    notes TEXT,
    styling_notes TEXT NOT NULL,
    label_text TEXT,
    fit TEXT,
    sheen TEXT,
    brand TEXT,
    wear_count INTEGER NOT NULL DEFAULT 0,
    last_worn TEXT,
    date_added TEXT NOT NULL DEFAULT (date('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS outfits (
    id INTEGER PRIMARY KEY NOT NULL,
    timestamp TEXT NOT NULL,
    prompt_message TEXT NOT NULL,
    aesthetic TEXT NOT NULL,
    explanation TEXT NOT NULL,
    missing TEXT,
    liked INTEGER DEFAULT NULL,
    CHECK (liked in (0, 1))
);

CREATE TABLE IF NOT EXISTS outfit_garments (
    outfit_id INTEGER NOT NULL,
    garment_id INTEGER NOT NULL,
    styling_advice TEXT,
    is_anchor INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (outfit_id, garment_id),
    FOREIGN KEY (outfit_id) REFERENCES outfits(id),
    FOREIGN KEY (garment_id) REFERENCES garments(id)
);

CREATE TABLE IF NOT EXISTS wears (
    id INTEGER PRIMARY KEY NOT NULL,
    outfit_id INTEGER NOT NULL,
    notes TEXT,
    date TEXT NOT NULL,
    FOREIGN KEY (outfit_id) REFERENCES outfits(id)
);

CREATE INDEX IF NOT EXISTS idx_outfit_garments_garment ON outfit_garments(garment_id);
