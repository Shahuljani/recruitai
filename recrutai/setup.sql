-- Run this in your Supabase SQL Editor

-- 1. Create Job Roles Table
CREATE TABLE job_roles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    user_id UUID NOT NULL, -- Links to the logged-in user
    title TEXT NOT NULL,
    description TEXT,
    file_url TEXT
);

-- 2. Create Candidates Table
CREATE TABLE candidates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    user_id UUID NOT NULL,
    name TEXT DEFAULT 'Unknown Candidate',
    email TEXT,
    job_role_id UUID REFERENCES job_roles(id),
    matched_role TEXT,
    score FLOAT,
    status TEXT CHECK (status IN ('Shortlisted', 'On Hold', 'Rejected')),
    resume_text TEXT,
    file_url TEXT
);

-- 3. Enable Row Level Security (RLS) - Optional for initial testing but recommended
ALTER TABLE job_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;

-- 4. Simple policy to allow users to see ONLY their own data
CREATE POLICY "Users can see their own jobs" ON job_roles
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can see their own candidates" ON candidates
    FOR ALL USING (auth.uid() = user_id);