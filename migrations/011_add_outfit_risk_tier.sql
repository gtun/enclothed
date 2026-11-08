-- The tier an AI outfit was suggested at (safe, stretch, bold). NULL for outfits saved before
-- tiers existed and for outfits the user put together themselves.
ALTER TABLE outfits ADD COLUMN risk_tier TEXT CHECK (risk_tier IN ('safe', 'stretch', 'bold'));
