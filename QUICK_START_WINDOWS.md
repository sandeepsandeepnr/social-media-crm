# Quick Start Guide for Windows - Phase-1a Setup

**Goal**: Get the Social Media CRM backend running locally in 30 minutes

---

## ✅ Prerequisites

- Windows 10/11
- Python 3.9+ installed ([Download](https://www.python.org/downloads/))
- Git installed ([Download](https://git-scm.com/download/win))
- One of:
  - Docker Desktop ([Download](https://www.docker.com/products/docker-desktop)) - RECOMMENDED
  - PostgreSQL 15 ([Download](https://www.postgresql.org/download/windows/))

---

## 🚀 FASTEST SETUP (Using Docker - 15 minutes)

### Step 1: Create PostgreSQL Container
```powershell
# Open PowerShell and run:
docker run --name social-crm-db `
  -e POSTGRES_USER=crm_user `
  -e POSTGRES_PASSWORD=crm_password `
  -e POSTGRES_DB=social_media_crm `
  -p 5432:5432 `
  -d postgres:15-alpine

# Verify it started
docker ps  # You should see social-crm-db running
```

**If Docker not installed**: Skip to "Manual PostgreSQL Setup" section below

### Step 2: Create Backend Directories
```powershell
# Navigate to project
cd D:\social-media-crm

# Create directory structure
$dirs = @(
    "backend\app\api",
    "backend\app\models",
    "backend\app\schemas", 
    "backend\app\services",
    "backend\app\integrations",
    "backend\app\utils",
    "backend\middleware",
    "backend\database",
    "backend\tests"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

# Create __init__.py files
$initDirs = @(
    "backend\app",
    "backend\app\api",
    "backend\app\models",
    "backend\app\schemas",
    "backend\app\services",
    "backend\app\integrations",
    "backend\app\utils",
    "backend\middleware",
    "backend\database",
    "backend\tests"
)

foreach ($dir in $initDirs) {
    New-Item -ItemType File -Path "$dir\__init__.py" -Force | Out-Null
}

Write-Host "✅ Backend directories created!"
```

### Step 3: Setup Python Virtual Environment
```powershell
# Navigate to backend
cd D:\social-media-crm\backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get execution policy error, run this FIRST:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt

# Should complete without errors
```

### Step 4: Create .env File
```powershell
# Copy example to actual .env
Copy-Item .env.example .env

# Edit the file (open with Notepad)
notepad .env
```

**Update these lines in .env:**
```
DATABASE_URL=postgresql://crm_user:crm_password@localhost:5432/social_media_crm
SECRET_KEY=your-dev-secret-key-change-in-production-12345678
WEBHOOK_VERIFY_TOKEN=webhook-token-123456
ENVIRONMENT=development
DEBUG=True
```

Save the file (Ctrl+S, then close)

### Step 5: Initialize Database Schema
```powershell
# Make sure you're in D:\social-media-crm\backend with venv activated

# Run SQL schema
# Option A: Using psql (if installed)
psql -U crm_user -d social_media_crm -f ..\database\schema.sql -h localhost

# Option B: Create a Python script to run SQL
# (We'll create this if psql doesn't work - see troubleshooting below)

# Verify tables were created
psql -U crm_user -d social_media_crm -h localhost -c "\dt"
# Should list: audit_logs, customers, interactions, platform_credentials, etc.
```

### Step 6: Start the Backend
```powershell
# Make sure venv is still activated
# Navigate to backend directory
cd D:\social-media-crm\backend

# Start the server
python main.py

# Expected output:
# 🚀 Starting Social Media CRM Backend
# Environment: development
# ✅ Database initialized successfully
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 7: Test the Backend
**In a NEW PowerShell window** (keep the first one running):
```powershell
# Test health endpoint
Invoke-WebRequest -Uri http://localhost:8000/health

# Should return: {"status": "ok", "timestamp": "...", "version": "1.0.0-alpha"}

# If you see this, CONGRATULATIONS! 🎉 Backend is running!
```

---

## 🔧 Manual PostgreSQL Setup (Without Docker)

If you don't want to use Docker:

### Download & Install PostgreSQL
1. Download from https://www.postgresql.org/download/windows/
2. Run installer
3. During installation:
   - **Password**: Remember this for the postgres user
   - **Port**: Keep as 5432
   - **Locale**: English
4. Click "Finish"

### Create Database & User
1. After installation, **pgAdmin** will open
2. Right-click "Servers" → "Create" → "Server"
   - Name: `local`
   - Hostname: `localhost`
   - Connect
3. Expand → Right-click "Databases" → "Create" → "Database"
   - Name: `social_media_crm`
   - Owner: `postgres`
   - Click "Save"
4. Right-click "Login/Group Roles" → "Create" → "Login Group Role"
   - Name: `crm_user`
   - Password: `crm_password`
   - Save
5. Assign privileges:
   - Right-click `social_media_crm` database
   - Properties → Security
   - Under Privileges for `crm_user`: Check all boxes
   - Save

### Run Database Schema
```powershell
# Using psql command
$env:PGPASSWORD = "crm_password"
psql -U crm_user -d social_media_crm -h localhost -f D:\social-media-crm\database\schema.sql

# If that doesn't work, use Python instead:
cd D:\social-media-crm\backend
python -c "
import subprocess
result = subprocess.run(['psql', '-U', 'crm_user', '-d', 'social_media_crm', '-h', 'localhost', '-f', '../database/schema.sql'], 
                       env={'PGPASSWORD': 'crm_password'})
print('Database initialized!' if result.returncode == 0 else 'Error running schema')
"
```

---

## 🆘 TROUBLESHOOTING

### Problem: "psql command not found"
**Solution**: PostgreSQL not in PATH
```powershell
# Find where PostgreSQL is installed (usually C:\Program Files\PostgreSQL\15\bin)
# Then run:
"C:\Program Files\PostgreSQL\15\bin\psql.exe" -U crm_user -d social_media_crm -h localhost -f ..\..\database\schema.sql
```

### Problem: "Database connection refused"
**Solution**: PostgreSQL not running
```powershell
# If using Docker:
docker ps  # Check if container is running
docker logs social-crm-db  # See error logs

# If using PostgreSQL directly:
# Check Services (Windows):
# Press Win+R → services.msc → Find "PostgreSQL" → Check if running
```

### Problem: "ModuleNotFoundError: No module named 'app'"
**Solution**: Backend structure not created correctly
```powershell
# Verify directories exist
Get-ChildItem D:\social-media-crm\backend\app

# Should show: api, integrations, models, schemas, services, utils folders
# If not, run Step 2 again
```

### Problem: "No module named 'config'"
**Solution**: Config file not found
```powershell
# Verify config.py exists
Get-ChildItem D:\social-media-crm\backend\config.py

# If missing, re-download from GitHub or create manually
```

### Problem: Activation script not found
**Solution**: Virtual environment not created
```powershell
# Check if venv exists
Get-ChildItem D:\social-media-crm\backend\venv

# If not:
cd D:\social-media-crm\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Problem: "Get-ExecutionPolicy" error
**Solution**: PowerShell execution policy
```powershell
# Run this FIRST:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# Then try activation again:
cd D:\social-media-crm\backend
.\venv\Scripts\Activate.ps1
```

---

## 📋 VERIFY SETUP CHECKLIST

Before moving to next steps, verify all of these work:

```powershell
# 1. Backend directories exist
Test-Path D:\social-media-crm\backend\app\api  # Should be True

# 2. Python 3.9+ installed
python --version  # Should show 3.9 or higher

# 3. Virtual environment created
Test-Path D:\social-media-crm\backend\venv  # Should be True

# 4. Dependencies installed
cd D:\social-media-crm\backend
.\venv\Scripts\Activate.ps1
pip list  # Should show fastapi, sqlalchemy, pydantic, etc.

# 5. .env file exists
Test-Path D:\social-media-crm\backend\.env  # Should be True

# 6. Database running
# If using Docker:
docker ps | grep social-crm-db  # Should show running
# If using PostgreSQL:
# Check in Services that PostgreSQL is running

# 7. Backend starts
python main.py
# Should output: "🚀 Starting Social Media CRM Backend"
# Press Ctrl+C to stop

# 8. Health endpoint works (in new terminal)
Invoke-WebRequest http://localhost:8000/health
# Should return 200 OK with health status
```

If all 8 checkpoints pass ✅, you're ready for Day 1-2 completion!

---

## 🎯 WHAT'S NEXT?

Once setup is complete, follow the [PHASE_1A_EXECUTION_STATUS.md](PHASE_1A_EXECUTION_STATUS.md) guide:

- **Day 3**: Implement Authentication (Endpoints 1-2)
- **Day 4**: Implement Platform Integration (Endpoints 3-5)
- **Day 5**: Implement Interaction Capture (Endpoints 6-8)
- And so on...

---

## 📞 HELP & RESOURCES

**Documentation**:
- [Full PHASE_1A Plan](IMMEDIATE_ACTION_PLAN.md)
- [API Specifications](docs/API_SPECIFICATION.md)
- [Architecture Overview](docs/ARCHITECTURE.md)

**Quick Links**:
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

---

**Time to completion**: ~30 minutes (fastest path with Docker)  
**Last Updated**: November 19, 2026  
**Status**: Ready to execute ✅

Good luck! 🚀 Once setup is done, you'll be ready to start building the API endpoints.
