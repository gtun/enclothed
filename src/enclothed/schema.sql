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
    date_added TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    set_id INTEGER REFERENCES sets(id),
    disowned_on TEXT,
    user_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    user_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS outfits (
    id INTEGER PRIMARY KEY NOT NULL,
    timestamp TEXT NOT NULL,
    prompt_message TEXT NOT NULL,
    aesthetic TEXT NOT NULL,
    explanation TEXT NOT NULL,
    missing TEXT,
    liked INTEGER DEFAULT NULL,
    user_id INTEGER REFERENCES users(id),
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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    style_notes TEXT,
    style_updated_at TEXT,
    language TEXT NOT NULL DEFAULT 'en-US'
);

INSERT OR IGNORE INTO users (id, username, is_admin) VALUES (1, 'owner', 1);
