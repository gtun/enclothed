CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    style_notes TEXT,
    style_updated_at TEXT
);

INSERT OR IGNORE INTO users (id, username, is_admin) VALUES (1, 'owner', 1);


UPDATE users
SET style_notes = (SELECT text FROM preferences WHERE id = 1),
    style_updated_at = (SELECT updated_at FROM preferences WHERE id = 1)
WHERE id = 1;

DROP TABLE preferences;
