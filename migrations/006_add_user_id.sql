ALTER TABLE garments ADD user_id INTEGER REFERENCES users(id);
ALTER TABLE sets ADD user_id INTEGER REFERENCES users(id);
ALTER TABLE outfits ADD user_id INTEGER REFERENCES users(id);

UPDATE garments SET user_id = 1;
UPDATE sets SET user_id = 1;
UPDATE outfits SET user_id = 1;
