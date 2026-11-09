-- Who made an outfit: 'ai' (suggested, including weigh's) or 'own' (put together by the user in the builder).
-- Until now only the request text hinted at it, and only when no occasion was typed.
ALTER TABLE outfits ADD COLUMN source TEXT NOT NULL DEFAULT 'ai' CHECK (source IN ('ai', 'own'));

-- Backfill. An outfit the user saved is alone at its timestamp and has no risk tier. Every AI reply before risk
-- tiers saved two to four outfits sharing one timestamp (unless validation dropped all but one), and every one
-- since has a tier. Weigh's outfits say so in their request.
UPDATE outfits SET source = 'own'
WHERE prompt_message = 'Put together myself'
   OR (risk_tier IS NULL
       AND prompt_message NOT LIKE 'Weighing: %'
       AND (SELECT COUNT(*) FROM outfits AS o2 WHERE o2.timestamp = outfits.timestamp) = 1);
