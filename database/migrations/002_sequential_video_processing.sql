-- Make video claiming idempotent and persist transcription diagnostics.
-- Run while connected to recipe_db.

BEGIN;

-- Preserve the newest status row if duplicates were created before uniqueness.
DELETE FROM public.video_log older
USING public.video_log newer
WHERE older.video_id = newer.video_id
  AND older.id < newer.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint constraint_info
        JOIN pg_attribute column_info
          ON column_info.attrelid = constraint_info.conrelid
         AND column_info.attname = 'video_id'
        WHERE constraint_info.conrelid = 'public.video_log'::regclass
          AND constraint_info.contype = 'u'
          AND constraint_info.conkey = ARRAY[column_info.attnum]::smallint[]
    ) THEN
        ALTER TABLE public.video_log
            ADD CONSTRAINT video_log_video_id_key UNIQUE (video_id);
    END IF;
END $$;

ALTER TABLE public.recipes
    ADD COLUMN IF NOT EXISTS transcript TEXT,
    ADD COLUMN IF NOT EXISTS transcript_language VARCHAR(32),
    ADD COLUMN IF NOT EXISTS transcript_source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS transcription_warning TEXT;

COMMIT;
