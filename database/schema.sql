-- Recipe Automation Database Schema
-- Database: recipes_db

-- =============================================
-- Recipes Table
-- =============================================
CREATE TABLE IF NOT EXISTS recipes (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    recipe_text TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrition JSONB,
    youtube_url VARCHAR(500),
    youtube_channel VARCHAR(255),
    thumbnail_url VARCHAR(500),
    docx_path VARCHAR(500),
    pdf_path VARCHAR(500),
    nextcloud_docx_url VARCHAR(500),
    nextcloud_pdf_url VARCHAR(500),
    transcript TEXT,
    transcript_language VARCHAR(32),
    transcript_source VARCHAR(50),
    transcription_warning TEXT,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- =============================================
-- Video Log Table
-- =============================================
CREATE TABLE IF NOT EXISTS video_log (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) UNIQUE NOT NULL,
    playlist_id VARCHAR(255),
    processed BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'pending',
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped'))
);

-- =============================================
-- Playlist Tracking Table
-- =============================================
CREATE TABLE IF NOT EXISTS playlist_tracking (
    id SERIAL PRIMARY KEY,
    playlist_id VARCHAR(255) UNIQUE NOT NULL,
    playlist_title VARCHAR(255),
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    video_count INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE
);

-- =============================================
-- Execution Log Table
-- =============================================
CREATE TABLE IF NOT EXISTS execution_log (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    workflow_name VARCHAR(100),
    workflow_id VARCHAR(255),
    n8n_execution_id VARCHAR(255),
    status VARCHAR(50),
    output_data JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- Indexes for Performance
-- =============================================
CREATE INDEX idx_recipes_video_id ON recipes(video_id);
CREATE INDEX idx_recipes_category ON recipes(category);
CREATE INDEX idx_recipes_processed ON recipes(processed);
CREATE INDEX idx_recipes_created_at ON recipes(created_at DESC);
CREATE INDEX idx_video_log_video_id ON video_log(video_id);
CREATE INDEX idx_video_log_status ON video_log(status);
CREATE INDEX idx_execution_log_recipe_id ON execution_log(recipe_id);
CREATE INDEX idx_execution_log_workflow_name ON execution_log(workflow_name);

-- =============================================
-- Views
-- =============================================

-- Recipes pending processing
CREATE OR REPLACE VIEW pending_recipes AS
SELECT r.id, r.title, r.category, r.created_at
FROM recipes r
WHERE r.processed = FALSE
ORDER BY r.created_at ASC;

-- Recent completed recipes
CREATE OR REPLACE VIEW recent_recipes AS
SELECT r.id, r.title, r.category, r.youtube_channel, r.nextcloud_docx_url, r.nextcloud_pdf_url, r.created_at
FROM recipes r
WHERE r.processed = TRUE
ORDER BY r.created_at DESC
LIMIT 20;

-- Processing statistics
CREATE OR REPLACE VIEW processing_stats AS
SELECT
    COUNT(*) as total_videos,
    COUNT(*) FILTER (WHERE processed = TRUE) as completed,
    COUNT(*) FILTER (WHERE processed = FALSE) as pending,
    COUNT(DISTINCT category) as categories
FROM recipes;
