#!/bin/bash

# Script to run the OCR Pipeline locally

echo "🚀 Starting OCR Pipeline locally..."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create a .env file with the following variables:"
    echo "  APP_DATABASE_URL=postgresql://user:pass@localhost/ocr"
    echo "  APP_PARASAIL_API_KEY=your-parasail-key"
    echo "  APP_AZURE_STORAGE_CONNECTION_STRING=your-connection-string"
    echo "  APP_AZURE_BLOB_CONTAINER=contracts"
    echo ""
    echo "You can copy .env.example to .env and fill in the values:"
    echo "  cp .env.example .env"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Load environment variables
echo "⚙️  Loading environment variables from .env..."
export $(grep -v '^#' .env | xargs)

# Run database migrations
echo "🗄️  Running database migrations..."
alembic upgrade head

# Start the application
echo ""
echo "✅ Starting application..."
echo "🌐 Server will be available at: http://localhost:8000"
echo "📚 API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run with uvicorn for development (hot reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
