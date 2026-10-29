ALTER TABLE garments
ADD set_id INTEGER REFERENCES sets(id);
