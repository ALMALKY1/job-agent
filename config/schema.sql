-- =============================================================================
-- Mohamed Job Agent — SQLite Schema
-- =============================================================================
-- This is the persistent job tracker database.
-- =============================================================================

CREATE TABLE IF NOT EXISTS jobs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identity
    linkedin_job_id       TEXT UNIQUE,
    dedup_key             TEXT UNIQUE,

    -- Core fields
    title                 TEXT NOT NULL,
    company               TEXT NOT NULL,
    location              TEXT,
    workplace_type        TEXT,  -- remote, hybrid, on-site

    -- URLs
    linkedin_url          TEXT,
    official_url          TEXT,

    -- Source
    source                TEXT DEFAULT 'linkedin_email',
    source_email_id       TEXT,

    -- ATS detection
    ats_platform          TEXT,

    -- Full description
    full_description      TEXT,
    requirements          TEXT,
    preferred_qualifications TEXT,
    language_requirements  TEXT,
    experience_requirements TEXT,
    visa_information       TEXT,
    relocation_information TEXT,
    description_source     TEXT,  -- official_careers, ats, linkedin, email

    -- AI Analysis
    fit_score             REAL,
    technical_score       REAL,
    career_score          REAL,
    relocation_score      REAL,
    visa_score            REAL,
    decision              TEXT,  -- APPLY, REVIEW, SKIP
    analysis_json         TEXT,  -- Full AI analysis JSON

    -- Visa & Relocation
    visa_sponsorship      TEXT,  -- CONFIRMED, LIKELY, UNKNOWN, UNLIKELY, NO
    relocation_support    TEXT,  -- CONFIRMED, LIKELY, UNKNOWN, NO

    -- Generated documents
    cv_file               TEXT,
    motivation_file       TEXT,
    cover_letter_file     TEXT,
    application_answers   TEXT,

    -- Status tracking
    status                TEXT DEFAULT 'NEW',
    -- NEW, FETCHING, ANALYZED, SKIPPED, SHORTLISTED,
    -- DOCUMENTS_READY, READY_TO_APPLY, APPLIED, FAILED,
    -- REJECTED, INTERVIEW, CLOSED

    -- Response tracking
    response_status       TEXT,  -- no_response, rejected, interview, offer
    application_notes     TEXT,

    -- Timestamps
    discovered_at         TEXT DEFAULT (datetime('now')),
    analyzed_at           TEXT,
    documents_generated_at TEXT,
    applied_at            TEXT,
    updated_at            TEXT DEFAULT (datetime('now')),

    -- Report tracking
    last_report_date      TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_decision ON jobs(decision);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
CREATE INDEX IF NOT EXISTS idx_jobs_dedup ON jobs(dedup_key);

-- Daily run log
CREATE TABLE IF NOT EXISTS daily_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date          TEXT NOT NULL,
    started_at        TEXT DEFAULT (datetime('now')),
    completed_at      TEXT,
    total_emails      INTEGER DEFAULT 0,
    total_jobs_found  INTEGER DEFAULT 0,
    duplicates_removed INTEGER DEFAULT 0,
    jobs_analyzed     INTEGER DEFAULT 0,
    jobs_skipped      INTEGER DEFAULT 0,
    jobs_review       INTEGER DEFAULT 0,
    jobs_shortlisted  INTEGER DEFAULT 0,
    documents_generated INTEGER DEFAULT 0,
    errors            INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'RUNNING',  -- RUNNING, COMPLETED, FAILED
    error_log         TEXT
);

-- Email processing log (avoid re-processing)
CREATE TABLE IF NOT EXISTS processed_emails (
    email_id          TEXT PRIMARY KEY,
    subject           TEXT,
    received_at       TEXT,
    processed_at      TEXT DEFAULT (datetime('now')),
    jobs_extracted    INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'PROCESSED'
);
