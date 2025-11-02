"""
WSGI wrapper that fixes sys.path before importing the main FastAPI app.
This runs before any imports, solving the /agents/python shadowing issue.
"""
import sys
import os

# Fix sys.path by removing /agents/python
sys.path = [p for p in sys.path if '/agents/python' not in p]

# Ensure site-packages is prioritized
for path in list(sys.path):
    if 'site-packages' in path and '/agents/python' not in path:
        if path in sys.path:
            sys.path.remove(path)
            sys.path.insert(0, path)
        break

print(f"[wsgi.py] Fixed sys.path - removed /agents/python", file=sys.stderr)
print(f"[wsgi.py] sys.path[0:3]: {sys.path[0:3]}", file=sys.stderr)

# Now import the actual app
from app.main import app

# Export for gunicorn
__all__ = ['app']
