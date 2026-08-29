import os
import sys
from pathlib import Path

# Add project root to sys.path for Vercel Serverless Function runtime
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import Flask app instance
from app import app

# WSGI entrypoint for Vercel
app = app

if __name__ == '__main__':
    app.run()
