-- Percent-encoded WebDAV URLs for long Cyrillic titles can exceed 500 chars
-- (each Cyrillic character becomes 6 bytes when percent-encoded), causing
-- "value too long for type character varying(500)" after a successful
-- Nextcloud upload. Widen both URL columns; recreate the dependent view.
-- Run while connected to recipe_db.

BEGIN;

DROP VIEW IF EXISTS recent_recipes;

ALTER TABLE recipes ALTER COLUMN nextcloud_docx_url TYPE VARCHAR(1500);
ALTER TABLE recipes ALTER COLUMN nextcloud_pdf_url TYPE VARCHAR(1500);

CREATE OR REPLACE VIEW recent_recipes AS
SELECT r.id, r.title, r.category, r.youtube_channel, r.nextcloud_docx_url, r.nextcloud_pdf_url, r.created_at
FROM recipes r
WHERE r.processed = TRUE
ORDER BY r.created_at DESC
LIMIT 20;

COMMIT;
