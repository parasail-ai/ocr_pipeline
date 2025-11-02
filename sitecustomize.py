"""
sitecustomize.py - Automatically run by Python interpreter on startup.

This fixes Azure App Service PYTHONPATH issues where /agents/python
shadows pip-installed packages, causing ImportError for typing_extensions.Sentinel
and other modern package features.
"""
import sys
import os

def fix_sys_path():
    """
    Remove Azure's /agents/python directory from sys.path to prevent
    it from shadowing properly installed packages in the virtual environment.
    """
    # Remove any paths containing '/agents/python'
    original_paths = sys.path[:]
    sys.path[:] = [p for p in sys.path if '/agents/python' not in p]
    
    # Ensure virtual environment site-packages is prioritized
    # Try to find the virtual environment's site-packages directory
    for path in original_paths:
        if 'site-packages' in path and '/agents/python' not in path:
            # Move it to the front if it's not already there
            if path in sys.path and sys.path[0] != path:
                sys.path.remove(path)
                sys.path.insert(0, path)
            break
    
    # Log the change for debugging (visible in Azure logs)
    if os.environ.get('WEBSITE_INSTANCE_ID'):  # Running on Azure
        print(f"[sitecustomize.py] Fixed sys.path - removed /agents/python paths", file=sys.stderr)
        print(f"[sitecustomize.py] New sys.path[0:3]: {sys.path[0:3]}", file=sys.stderr)

# Run the fix immediately when this module is imported
fix_sys_path()
