#!/bin/bash
echo "Starting ML Converter Development Server"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

mkdir -p tmp

echo "Starting Flask development server..."
echo "Access the application at: http://localhost:5000"
python src/app.py
