# Mohamed Job Agent

AI-powered automated job search and application system for embedded software engineering roles in Europe.

## Overview

This system automatically:
- Reads LinkedIn Job Alert emails from Gmail
- Extracts and deduplicates individual job listings
- Retrieves full job descriptions from official sources
- Analyzes each job against Mohamed Almalky's career profile
- Evaluates visa sponsorship and relocation possibilities
- Performs ATS requirements analysis using OpenAI
- Generates ATS-optimized DOCX documents & converts them to final PDF files via headless LibreOffice
- Validates PDF text readability and keyword matching via `pdftotext` (0–100 ATS score)
- Automatically cleans up intermediate DOCX build artifacts
- Tracks every job through the application lifecycle
- Prepares browser-assisted ATS form filling (stops before submission)

## Architecture

```
~/job-agent/
├── career-profile/        # Immutable master career profile (JSON)
├── config/                # Database schema, settings
├── data/                  # SQLite database (gitignored)
├── docker/                # Docker configurations
├── generated/             # Generated application documents (gitignored)
│   ├── cv/                # Tailored CV PDFs and DOCX builds
│   ├── motivation/        # Motivation Letter PDFs and DOCX builds
│   └── applications/      # Application answers JSON
├── browser-agent/         # Playwright browser automation
├── logs/                  # Daily reports and logs (gitignored)
├── n8n/
│   ├── workflows/         # Exportable n8n workflow JSON
│   └── CREDENTIAL_SETUP.md
├── prompts/               # AI prompt templates (job_analysis, ats_analysis, etc.)
├── scripts/               # Python modules
│   ├── pipeline.py        # Main orchestrator
│   ├── email_parser.py    # LinkedIn email parser
│   ├── db_manager.py      # SQLite database manager
│   ├── ai_analyzer.py     # AI analysis & ATS prompt builder
│   ├── job_retriever.py   # Job description retrieval
│   ├── doc_generator.py   # ATS DOCX generation
│   ├── pdf_converter.py   # LibreOffice headless PDF converter
│   ├── ats_validator.py   # PDF pdftotext ATS validator
│   └── daily_report.py    # Daily summary reports
├── templates/             # Document templates
└── tests/
    ├── fixtures/          # Test email fixtures
    └── test_all.py        # Test suite (52 tests)
```

## Quick Start

### 1. Prerequisites

- Ubuntu 22.04 LTS
- Docker Engine (from official Docker APT repo)
- n8n Community Edition running on `http://localhost:5678`
- Python 3.10+
- `libreoffice` (for headless DOCX → PDF conversion)
- `poppler-utils` (for `pdftotext` ATS text extraction)

### 2. Setup

```bash
# Clone/navigate to the project
cd ~/job-agent

# Run setup script
./setup-docker-n8n.sh

# Copy environment template
cp .env.example .env

# Initialize the database
python3 scripts/db_manager.py

# Run tests
python3 -m unittest tests.test_all -v

# Run the pipeline with test fixtures
python3 scripts/pipeline.py
```

### 3. Configure n8n Credentials

See [n8n/CREDENTIAL_SETUP.md](n8n/CREDENTIAL_SETUP.md) for detailed instructions.

**Required credentials:**
1. **Gmail OAuth2** — for reading LinkedIn alert emails
2. **OpenAI API Key** — for AI job analysis and document generation

**To import the workflow:**
1. Open n8n at http://localhost:5678
2. Menu → Import from File → select `n8n/workflows/daily_pipeline.json`
3. Connect credentials to each node
4. Activate the workflow

## Document Generation Pipeline

```
Job Description
  → OpenAI ATS Requirements Analysis (ats_analysis.md)
  → Tailored Content (Strict Anti-Fabrication Rules)
  → Single-Column ATS-Safe DOCX (python-docx, Calibri 11pt, 1" margins)
  → LibreOffice Headless PDF Conversion (libreoffice --headless)
  → PDF ATS Validation (pdftotext extraction, section check, 0-100 ATS score)
  → Intermediate DOCX Cleanup (unless DEBUG_KEEP_DOCX=true)
  → Final PDF Application Files (Status: DOCUMENTS_READY)
```

## Configuration

### Scoring Thresholds
- **≥ 80**: SHORTLISTED (apply)
- **65–79**: REVIEW (manual decision)
- **< 65**: SKIP

### ATS Platforms Detected
Workday, Greenhouse, Lever, SmartRecruiters, Teamtailor, SuccessFactors, Ashby, Personio

## Career Profile

The immutable master profile is at `career-profile/mohamed_almalky.json`.

Skill levels: **EXPERIENCE** | **INTEREST** | **LEARNING** | **NOT_EXPERIENCED**

**The system never fabricates skills, experience, or credentials.**

## Security

- No credentials stored in source code
- `.env` is gitignored
- n8n handles OAuth tokens
- API keys via environment variables
- No secrets printed in logs

## Daily Schedule

The n8n workflow runs at **8:00 AM Africa/Cairo** daily.

## License

Private project — Mohamed Almalky
