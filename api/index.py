import sys
from pathlib import Path

# Ensure project root is in Python sys.path for Vercel Serverless environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the initialized Flask application instance
from app import app

# Expose app as the WSGI callable for Vercel Python runtime
if __name__ == '__main__':
    app.run()
