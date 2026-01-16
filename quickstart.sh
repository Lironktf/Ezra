#!/bin/bash

echo "🚀 GitHub Expert Finder - Quick Start"
echo "======================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys before continuing!"
    echo "   - BROWSERBASE_API_KEY"
    echo "   - BROWSERBASE_PROJECT_ID"
    echo "   - OPENAI_API_KEY"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the environment: source venv/bin/activate"
echo "2. Start Qdrant: docker run -p 6333:6333 qdrant/qdrant"
echo "   (or use --memory flag to skip Docker)"
echo "3. Run the pipeline: python main.py pipeline -q 'Your question here'"
echo ""
echo "Quick test (in-memory mode):"
echo "  python main.py pipeline -m -q 'React hooks best practices'"
echo ""
