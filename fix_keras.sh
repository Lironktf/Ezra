#!/bin/bash
# Fix for Keras 3 compatibility issue with sentence-transformers

echo "🔧 Fixing Keras compatibility issue..."

# Option 1: Set environment variable to disable TensorFlow in transformers
export TF_ENABLE_ONEDNN_OPTS=0
export TRANSFORMERS_OFFLINE=0

# Option 2: Install tf-keras for backwards compatibility
pip install tf-keras --quiet

echo "✅ Fixed! Now run:"
echo "   export TF_ENABLE_ONEDNN_OPTS=0"
echo "   python3 main.py embed"
