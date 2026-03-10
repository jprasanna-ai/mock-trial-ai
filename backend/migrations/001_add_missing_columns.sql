-- Migration 001: Add missing columns and tables for full DB persistence
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor)

-- 1. Add missing columns to prep_materials
ALTER TABLE prep_materials ADD COLUMN IF NOT EXISTS opening_plaintiff TEXT;
ALTER TABLE prep_materials ADD COLUMN IF NOT EXISTS user_notes JSONB DEFAULT '{}';

-- 2. Create live_scores table for persisting scoring data across restarts
CREATE TABLE IF NOT EXISTS live_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    scores JSONB NOT NULL DEFAULT '{}',
    phase TEXT,
    transcript_length INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id)
);

-- 3. Performance indexes
CREATE INDEX IF NOT EXISTS idx_live_scores_session ON live_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_prep_case ON agent_prep_materials(case_id);
CREATE INDEX IF NOT EXISTS idx_prep_materials_case ON prep_materials(case_id);
CREATE INDEX IF NOT EXISTS idx_scoring_results_session ON scoring_results(session_id);
CREATE INDEX IF NOT EXISTS idx_ballots_scoring_result ON ballots(scoring_result_id);

-- 4. Enable RLS on new table (match existing security pattern)
ALTER TABLE live_scores ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "Service role full access on live_scores"
    ON live_scores FOR ALL
    USING (true)
    WITH CHECK (true);

-- Verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'prep_materials' 
ORDER BY ordinal_position;

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'live_scores' 
ORDER BY ordinal_position;
