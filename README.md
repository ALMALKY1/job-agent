# Mohamed Job Agent

AI-powered automated job search and application system for embedded software engineering roles in Europe.

## Overview

This system automatically:
- Reads LinkedIn Job Alert emails from Gmail
- Extracts and deduplicates individual job listings
- Retrieves full job descriptions from official sources
- Analyzes each job against Mohamed Almalky's career profile
- Evaluates visa sponsorship and relocation possibilities
- Generates tailored CVs, Motivation Letters, and application answers
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
│   ├── cv/                # Tailored CVs
│   ├── motivation/        # Motivation Letters
│   └── applications/      # Application answers
├── browser-agent/         # Playwright browser automation
├── logs/                  # Daily reports and logs (gitignored)
├── n8n/
│   ├── workflows/         # Exportable n8n workflow JSON
│   └── CREDENTIAL_SETUP.md
├── prompts/               # AI prompt templates
├── scripts/               # Python modules
│   ├── pipeline.py        # Main orchestrator
│   ├── email_parser.py    # LinkedIn email parser
│   ├── db_manager.py      # SQLite database manager
│   ├── ai_analyzer.py     # AI analysis integration
│   ├── job_retriever.py   # Job description retrieval
│   ├── doc_generator.py   # Document generation
│   └── daily_report.py    # Daily summary reports
├── templates/             # Document templates
└── tests/
    ├── fixtures/          # Test email fixtures
    └── test_all.py        # Test suite (44 tests)
```

## Quick Start

### 1. Prerequisites

- Ubuntu 22.04 LTS
- Docker Engine (from official Docker APT repo)
- n8n Community Edition running on `http://localhost:5678`
- Python 3.10+

### 2. Setup

```bash
# Clone/navigate to the project
cd ~/job-agent

# Copy environment template
cp .env.example .env
# Edit .env with your actual values (OpenAI API key, etc.)

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

### 4. Install Optional Dependencies

```bash
# For DOCX document generation
pip install python-docx

# For browser automation (later phase)
pip install playwright
playwright install
```

## Pipeline Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Email Ingestion | Read Gmail, identify LinkedIn alerts | ✅ Working (needs Gmail OAuth) |
| Job Extraction | Parse HTML/text emails, extract jobs | ✅ Working |
| Deduplication | LinkedIn Job ID + fallback key | ✅ Working |
| Job Description | Retrieve from official/ATS sources | ✅ Framework ready |
| AI Analysis | Score fit, visa, relocation | ✅ Schema + mock ready (needs OpenAI) |
| Filtering | Apply/Review/Skip thresholds | ✅ Working |
| CV Generation | Tailored CV per job | ✅ Framework ready (needs OpenAI) |
| Motivation Letter | Tailored letter per job | ✅ Framework ready (needs OpenAI) |
| Application Answers | Q&A with NEEDS_USER_INPUT | ✅ Framework ready (needs OpenAI) |
| Daily Report | Summary with match details | ✅ Working |
| Browser Automation | Playwright ATS filling | ✅ Foundation ready |
| Application Tracker | SQLite with full lifecycle | ✅ Working |

## Configuration

### Scoring Thresholds
- **≥ 80**: SHORTLISTED (apply)
- **65–79**: REVIEW (manual decision)
- **< 65**: SKIP

### Immediate Rejection Signals
- Citizenship requirement incompatible with candidate
- Mandatory security clearance unavailable
- Mandatory native language requirement
- Role unrelated to embedded/software
- Required experience significantly beyond profile

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
