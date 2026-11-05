-- No CHECK on the values: SQLite can't change one without rebuilding the table, and
-- models.Language already limits what the app accepts.
ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'en-US';
