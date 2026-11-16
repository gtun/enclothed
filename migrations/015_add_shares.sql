-- Share links: a frozen copy of a garment, or of an outfit and its garments, that anyone with the link
-- can see until expires_at. snapshot is JSON holding only what the shared page shows, with no ids or names, so
-- later edits never change a share. Its photos are copies too, in data/thumbs/shares/<token>/.
-- user_id is who shared it, for the server only: it's never sent to the page.
CREATE TABLE shares (
    token TEXT PRIMARY KEY NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK (kind IN ('garment', 'outfit')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    snapshot TEXT NOT NULL
);
