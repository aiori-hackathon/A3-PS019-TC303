import os
import sys
from pathlib import Path

# Ensure root directory is on Python search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Expose ASGI application for Vercel Serverless Function
from backend.api.main import app
