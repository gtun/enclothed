CREATE TABLE IF NOT EXISTS preferences (
    -- The owner's own description of their tastes and needs, sent with outfit requests.
    -- One row (id = 1) until accounts exist; then it gains a user_id like the other tables.
    id INTEGER PRIMARY KEY NOT NULL CHECK (id = 1),
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
