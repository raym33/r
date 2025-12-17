-- AGI Memory System - PostgreSQL + pgvector initialization
-- Based on QuixiAI/agi-memory architecture

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Memory types enum
CREATE TYPE memory_type AS ENUM (
    'working',
    'episodic',
    'semantic',
    'procedural',
    'strategic'
);

-- Main memories table with vector embeddings
CREATE TABLE IF NOT EXISTS memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type memory_type NOT NULL DEFAULT 'semantic',
    importance FLOAT DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    embedding vector(384),  -- For all-MiniLM-L6-v2 embeddings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    decay_rate FLOAT DEFAULT 0.01,
    metadata JSONB,
    tags TEXT[]
);

-- Beliefs/preferences table
CREATE TABLE IF NOT EXISTS beliefs (
    id SERIAL PRIMARY KEY,
    belief TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    source TEXT,
    embedding vector(384),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Goals and intentions
CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    goal TEXT NOT NULL,
    priority FLOAT DEFAULT 0.5 CHECK (priority >= 0 AND priority <= 1),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    parent_goal_id INTEGER REFERENCES goals(id),
    embedding vector(384),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Conversation history for episodic memory
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    embedding vector(384),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Memory links/relationships (graph structure)
CREATE TABLE IF NOT EXISTS memory_links (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    strength FLOAT DEFAULT 0.5 CHECK (strength >= 0 AND strength <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(source_id, target_id, relationship)
);

-- Identity persistence
CREATE TABLE IF NOT EXISTS identity (
    id SERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Emotional state tracking
CREATE TABLE IF NOT EXISTS emotional_states (
    id SERIAL PRIMARY KEY,
    state JSONB NOT NULL,  -- {"happiness": 0.7, "curiosity": 0.8, ...}
    context TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_content_trgm ON memories USING gin(content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority DESC);

CREATE INDEX IF NOT EXISTS idx_beliefs_confidence ON beliefs(confidence DESC);

-- Vector similarity indexes (IVFFlat for faster approximate search)
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_beliefs_embedding ON beliefs
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_conversations_embedding ON conversations
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Functions for memory operations

-- Function to update last_accessed and access_count
CREATE OR REPLACE FUNCTION update_memory_access()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE memories
    SET last_accessed = NOW(), access_count = access_count + 1
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to apply memory decay
CREATE OR REPLACE FUNCTION apply_memory_decay()
RETURNS void AS $$
BEGIN
    UPDATE memories
    SET importance = GREATEST(0.01, importance * (1 - decay_rate))
    WHERE importance > 0.01;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar memories by embedding
CREATE OR REPLACE FUNCTION find_similar_memories(
    query_embedding vector(384),
    limit_count INTEGER DEFAULT 5,
    min_similarity FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    id INTEGER,
    content TEXT,
    memory_type memory_type,
    importance FLOAT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        1 - (m.embedding <=> query_embedding) as similarity
    FROM memories m
    WHERE m.embedding IS NOT NULL
      AND 1 - (m.embedding <=> query_embedding) >= min_similarity
    ORDER BY m.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to consolidate memories (merge similar ones)
CREATE OR REPLACE FUNCTION consolidate_memories(
    similarity_threshold FLOAT DEFAULT 0.9
)
RETURNS INTEGER AS $$
DECLARE
    consolidated_count INTEGER := 0;
BEGIN
    -- Mark highly similar memories for consolidation
    -- This is a simplified version - full implementation would merge content
    WITH similar_pairs AS (
        SELECT
            m1.id as keep_id,
            m2.id as remove_id
        FROM memories m1
        JOIN memories m2 ON m1.id < m2.id
        WHERE m1.embedding IS NOT NULL
          AND m2.embedding IS NOT NULL
          AND 1 - (m1.embedding <=> m2.embedding) >= similarity_threshold
    )
    DELETE FROM memories WHERE id IN (SELECT remove_id FROM similar_pairs);

    GET DIAGNOSTICS consolidated_count = ROW_COUNT;
    RETURN consolidated_count;
END;
$$ LANGUAGE plpgsql;

-- Insert default identity
INSERT INTO identity (key, value) VALUES
    ('name', '"R"'),
    ('version', '"0.3.2"'),
    ('personality', '{"traits": ["helpful", "direct", "technical"], "style": "concise"}'),
    ('created_at', to_jsonb(NOW()))
ON CONFLICT (key) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rcli;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rcli;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rcli;
