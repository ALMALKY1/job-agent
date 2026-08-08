#!/usr/bin/env bash
# =============================================================================
# Mohamed Job Agent — Project Setup Script
# =============================================================================
# Run this after cloning to set up the Python environment and database.
#
# Usage: ./setup.sh
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# Step 1: Check Python
# ---------------------------------------------------------------------------
info "Checking Python..."
python3 --version

# ---------------------------------------------------------------------------
# Step 2: Install python3-venv if needed
# ---------------------------------------------------------------------------
if ! python3 -m venv --help &>/dev/null; then
    info "Installing python3-venv..."
    sudo apt install -y python3-venv python3.12-venv 2>/dev/null || \
    sudo apt install -y python3-venv 2>/dev/null || \
    warn "Could not install python3-venv. Install it manually: sudo apt install python3-venv"
fi

# ---------------------------------------------------------------------------
# Step 3: Create virtual environment
# ---------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
    info "  ✅ Virtual environment created."
else
    info "  Virtual environment already exists."
fi

# ---------------------------------------------------------------------------
# Step 4: Install dependencies
# ---------------------------------------------------------------------------
info "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
info "  ✅ Dependencies installed."

# ---------------------------------------------------------------------------
# Step 5: Create .env if it doesn't exist
# ---------------------------------------------------------------------------
if [ ! -f ".env" ]; then
    cp .env.example .env
    info "  ✅ Created .env from .env.example — edit it with your actual values."
else
    info "  .env already exists."
fi

# ---------------------------------------------------------------------------
# Step 6: Initialize database
# ---------------------------------------------------------------------------
info "Initializing database..."
python3 scripts/db_manager.py
info "  ✅ Database ready."

# ---------------------------------------------------------------------------
# Step 7: Run tests
# ---------------------------------------------------------------------------
info "Running tests..."
python3 -m unittest tests.test_all -v
info "  ✅ All tests passed."

# ---------------------------------------------------------------------------
# Step 8: Run pipeline with fixtures
# ---------------------------------------------------------------------------
info "Running pipeline with test fixtures..."
# Reset DB for clean test
rm -f data/jobs.db
python3 scripts/db_manager.py
python3 scripts/pipeline.py

echo ""
info "============================================="
info "  ✅ Setup complete!"
info "============================================="
info ""
info "Next steps:"
info "  1. Edit .env with your OpenAI API key"
info "  2. Set up Gmail OAuth2 in n8n (see n8n/CREDENTIAL_SETUP.md)"
info "  3. Import workflow: n8n → Menu → Import from File → n8n/workflows/daily_pipeline.json"
info "  4. Activate the virtual environment: source venv/bin/activate"
info ""
