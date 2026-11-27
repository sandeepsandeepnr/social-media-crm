#!/bin/bash
# Social Media CRM - Quick Start Setup Script
# For Linux/Mac Users (Windows users, follow manual steps in README)

echo "🚀 Social Media CRM - Phase-1a Setup"
echo "========================================"
echo ""

# Check Python installation
echo "✓ Checking Python installation..."
python3 --version || { echo "❌ Python 3 not found. Please install Python 3.11+"; exit 1; }

# Navigate to project
echo "✓ Navigating to project directory..."
cd "$(dirname "$0")" || exit

# Create virtual environment
echo "✓ Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "✓ Installing Python dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Create .env file
echo "✓ Creating .env configuration file..."
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "⚠️  MANUAL STEP: Edit backend/.env with your database credentials"
    echo "   - DATABASE_URL: postgresql://crm_user:password@localhost:5432/social_media_crm"
    echo "   - SECRET_KEY: (keep as is or generate a new random string)"
    echo "   - Other API keys: Add when you have Facebook/Instagram credentials"
else
    echo "   .env already exists"
fi

echo ""
echo "✅ Setup Complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Create PostgreSQL database and user:"
echo "      createdb -U postgres social_media_crm"
echo "      createuser -U postgres crm_user"
echo "      (Or configure manually in PostgreSQL)"
echo ""
echo "   2. Update backend/.env with database credentials"
echo ""
echo "   3. Apply database schema:"
echo "      psql -U crm_user -d social_media_crm < database/schema.sql"
echo ""
echo "   4. Start backend server:"
echo "      cd backend && python main.py"
echo ""
echo "   5. In another terminal, start frontend:"
echo "      cd frontend && python -m http.server 8080"
echo ""
echo "   6. Access application:"
echo "      Frontend: http://localhost:8080/login.html"
echo "      API Docs: http://localhost:8000/api/docs"
echo ""
echo "📚 Documentation: Read IMMEDIATE_ACTION_PLAN.md for detailed steps"
echo ""
