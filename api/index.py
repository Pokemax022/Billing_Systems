import os
import sys
from pathlib import Path

# Ensure project root is in Python sys.path for Vercel Serverless environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the initialized Flask application instance
from app import app

# Expose WSGI handler aliases for all Vercel Python runtimes
handler = app
application = app

if __name__ == '__main__':
    app.run()
