-- Recipe search support for Telegram bot.
-- Adds fuzzy text indexes and short-lived numbered search sessions.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS telegram_search_sessions (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    result_number INTEGER NOT NULL CHECK (result_number > 0),
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    query TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telegram_search_sessions_chat_number
    ON telegram_search_sessions(chat_id, result_number, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_telegram_search_sessions_created_at
    ON telegram_search_sessions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recipes_title_trgm
    ON recipes USING gin ((lower(title)) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_recipes_category_trgm
    ON recipes USING gin ((lower(COALESCE(category, ''))) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_recipes_description_trgm
    ON recipes USING gin ((lower(COALESCE(description, ''))) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_recipes_ingredients_trgm
    ON recipes USING gin ((lower(COALESCE(ingredients::text, ''))) gin_trgm_ops);

ALTER TABLE telegram_search_sessions OWNER TO recipe_user;
ALTER SEQUENCE telegram_search_sessions_id_seq OWNER TO recipe_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE telegram_search_sessions TO recipe_user;
GRANT USAGE, SELECT ON SEQUENCE telegram_search_sessions_id_seq TO recipe_user;

COMMIT;
