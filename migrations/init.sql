
-- Drop existing tables in reverse order of dependency to avoid errors.
-- The CASCADE option will automatically remove dependent objects.
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS reactions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS confessions CASCADE;
; -- To clean up old table if it exists

-- Recreate tables with the new schema

CREATE TABLE IF NOT EXISTS confessions (
    id SERIAL PRIMARY KEY,
    author_id BIGINT NOT NULL, -- Raw user ID for easy lookups
    author_user_id TEXT NOT NULL, -- Original encrypted ID
    channel_chat_id BIGINT NOT NULL,
    channel_message_id INTEGER NOT NULL,
    category VARCHAR(32) NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    last_notified_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reactions (
    id SERIAL PRIMARY KEY,
    confession_id INTEGER NOT NULL REFERENCES confessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reaction_type VARCHAR(32) NOT NULL,
    reacted_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(confession_id, user_id, reaction_type)
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    confession_id INTEGER NOT NULL REFERENCES confessions(id) ON DELETE CASCADE,
    commenter_user_id BIGINT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
