#!/bin/bash
# start_webapp.sh — Launch the R5 web frontend using the correct venv
# Usage: ./start_webapp.sh
#        ./start_webapp.sh --port 5051

cd "$(dirname "$0")"

VENV="webapp/venv"
if [ ! -f "$VENV/bin/python3" ]; then
    echo "❌ webapp venv not found at $VENV"
    exit 1
fi

echo "🏇  Starting R5 Web Frontend..."
echo "   Python: $VENV/bin/python3"
echo "   URL:    http://localhost:5050"
echo ""

source "$VENV/bin/activate"
exec python3 webapp/app.py "$@"
