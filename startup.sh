#!/bin/bash
# Azure App Service startup script to fix PYTHONPATH before starting gunicorn

echo "=== Custom Startup Script ==="
echo "Original PYTHONPATH: $PYTHONPATH"

# Copy sitecustomize.py to site-packages so it runs automatically
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "Site-packages location: $SITE_PACKAGES"

if [ -f "/tmp/8de19ecaa12a552/sitecustomize.py" ]; then
    echo "Copying sitecustomize.py to site-packages..."
    cp /tmp/8de19ecaa12a552/sitecustomize.py "$SITE_PACKAGES/" 2>/dev/null || true
fi

# Alternative: Fix PYTHONPATH directly by removing /agents/python
export PYTHONPATH=$(echo "$PYTHONPATH" | tr ':' '\n' | grep -v '/agents/python' | tr '\n' ':' | sed 's/:$//')
echo "Fixed PYTHONPATH: $PYTHONPATH"

echo "Starting gunicorn..."
exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind=0.0.0.0:8000
