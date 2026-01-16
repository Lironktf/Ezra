#!/bin/bash

echo "=================================="
echo "GitHub Expert Finder - Web UI"
echo "=================================="
echo ""

# Check if Groq API key is set
if grep -q "your_groq_api_key_here" .env 2>/dev/null; then
    echo "⚠️  WARNING: Groq API key not configured!"
    echo ""
    echo "To get your FREE Groq API key:"
    echo "1. Go to https://console.groq.com/keys"
    echo "2. Sign up (it's free!)"
    echo "3. Create an API key"
    echo "4. Add to .env: GROQ_API_KEY=gsk_your_key_here"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing web dependencies..."
    pip3 install flask flask-cors groq
fi

echo ""
echo "🚀 Starting web server..."
echo "📍 Open your browser to: http://localhost:5000"
echo ""

cd web && python3 app.py
