-- The last time mend asked the LLM about this garment, so a bulk run doesn't pay for it twice.
ALTER TABLE garments ADD COLUMN mended_on TEXT;
