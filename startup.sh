#!/bin/bash
# Azure App Service startup script to fix PYTHONPATH before starting gunicorn

echo "=== Custom Startup Script ==="
echo "Original PYTHONPATH: $PYTHONPATH"
echo "Working directory: $(pwd)"

# Copy sitecustomize.py to site-packages so it runs automatically
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "Site-packages location: $SITE_PACKAGES"

# Find sitecustomize.py in the current deployment directory
if [ -f "sitecustomize.py" ]; then
    echo "Copying sitecustomize.py from $(pwd)/sitecustomize.py to site-packages..."
    cp sitecustomize.py "$SITE_PACKAGES/" 2>/dev/null || true
    echo "Copy result: $?"
else
    echo "WARNING: sitecustomize.py not found in $(pwd)"
fi

# Fix PYTHONPATH directly by removing /agents/python
export PYTHONPATH=$(echo "$PYTHONPATH" | tr ':' '\n' | grep -v '/agents/python' | tr '\n' ':' | sed 's/:$//')
echo "Fixed PYTHONPATH: $PYTHONPATH"

echo "Starting gunicorn..."
exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind=0.0.0.0:8000
