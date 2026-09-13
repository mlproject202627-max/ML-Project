#!/bin/bash
# =============================================================================
# SENTINEL UEBA - Development Environment Setup Script
# =============================================================================
# This script sets up the development environment for the Sentinel project.
# It must be run from the project root directory.
#
# Prerequisites:
#   - PostgreSQL 15+ installed and running
#   - Python 3.11+ installed
#   - Node.js 18+ installed
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  SENTINEL UEBA - Development Setup${NC}"
echo -e "${CYAN}=============================================${NC}"
echo ""

# ── Step 1: PostgreSQL Service ─────────────────────────────────────────────
echo -e "${YELLOW}[1/8] Checking PostgreSQL service...${NC}"
if systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}  ✓ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}  → Starting PostgreSQL...${NC}"
    systemctl enable --now postgresql
    echo -e "${GREEN}  ✓ PostgreSQL started${NC}"
fi

# ── Step 2: Create PostgreSQL User ─────────────────────────────────────────
echo -e "${YELLOW}[2/8] Creating PostgreSQL user...${NC}"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='sentinel'" | grep -q 1; then
    echo -e "${GREEN}  ✓ User 'sentinel' already exists${NC}"
else
    sudo -u postgres psql -c "CREATE USER sentinel WITH PASSWORD 'sentinel_secret' CREATEDB;"
    echo -e "${GREEN}  ✓ User 'sentinel' created${NC}"
fi

# ── Step 3: Create PostgreSQL Database ─────────────────────────────────────
echo -e "${YELLOW}[3/8] Creating PostgreSQL database...${NC}"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='sentinel_db'" | grep -q 1; then
    echo -e "${GREEN}  ✓ Database 'sentinel_db' already exists${NC}"
else
    sudo -u postgres createdb -O sentinel sentinel_db
    echo -e "${GREEN}  ✓ Database 'sentinel_db' created${NC}"
fi

# ── Step 4: Verify Connection ──────────────────────────────────────────────
echo -e "${YELLOW}[4/8] Verifying database connection...${NC}"
if PGPASSWORD=sentinel_secret psql -U sentinel -h localhost -d sentinel_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Database connection verified${NC}"
else
    echo -e "${RED}  ✗ Cannot connect to database. Check pg_hba.conf for md5/scram-sha-256 auth.${NC}"
    echo -e "${YELLOW}  → You may need to update /etc/postgresql/17/main/pg_hba.conf:${NC}"
    echo -e "${YELLOW}    Replace 'peer' with 'md5' for local connections, then restart PostgreSQL.${NC}"
    exit 1
fi

# ── Step 5: Backend Environment ────────────────────────────────────────────
echo -e "${YELLOW}[5/8] Setting up backend environment...${NC}"
cd backend

if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random JWT secret
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/CHANGE_ME_TO_A_RANDOM_SECRET_KEY/$JWT_SECRET/" .env
    echo -e "${GREEN}  ✓ .env created with generated JWT secret${NC}"
else
    echo -e "${GREEN}  ✓ .env already exists${NC}"
fi

# ── Step 6: Python Virtual Environment ─────────────────────────────────────
echo -e "${YELLOW}[6/8] Setting up Python virtual environment...${NC}"
if [ ! -d venv ]; then
    python3 -m venv venv
    echo -e "${GREEN}  ✓ Virtual environment created${NC}"
fi
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q
echo -e "${GREEN}  ✓ Python dependencies installed${NC}"

# ── Step 7: Database Migrations ────────────────────────────────────────────
echo -e "${YELLOW}[7/8] Running database migrations...${NC}"
alembic upgrade head 2>/dev/null || echo -e "${YELLOW}  → Auto-generating initial migration...${NC}"
alembic revision --autogenerate -m "initial tables" 2>/dev/null || true
alembic upgrade head
echo -e "${GREEN}  ✓ Database migrations applied${NC}"

# ── Step 8: Seed Demo Data ─────────────────────────────────────────────────
echo -e "${YELLOW}[8/8] Seeding demo data...${NC}"
if [ -f scripts/seed_data.py ]; then
    python scripts/seed_data.py
    echo -e "${GREEN}  ✓ Demo data seeded${NC}"
else
    echo -e "${YELLOW}  → seed_data.py not found, skipping...${NC}"
fi

cd ..

# ── Frontend Setup ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Setting up frontend...${NC}"
npm install 2>/dev/null
echo -e "${GREEN}  ✓ Frontend dependencies installed${NC}"

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}=============================================${NC}"
echo -e "${GREEN}  ✓ Setup complete!${NC}"
echo -e "${CYAN}=============================================${NC}"
echo ""
echo -e "  ${YELLOW}Database:${NC}  postgresql://sentinel:***@localhost:5432/sentinel_db"
echo -e "  ${YELLOW}Backend:${NC}   cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo -e "  ${YELLOW}Frontend:${NC}  npm run dev"
echo -e "  ${YELLOW}ML Train:${NC}  cd backend && source venv/bin/activate && python ml/train.py"
echo ""
echo -e "  ${YELLOW}Demo Accounts:${NC}"
echo -e "    Admin:   admin@sentinel.demo / Admin123!"
echo -e "    Analyst: sarah.chen@sentinel.demo / Analyst123!"
echo -e "    Viewer:  viewer@sentinel.demo / Viewer123!"
echo ""
