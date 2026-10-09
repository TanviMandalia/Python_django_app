#!/usr/bin/env bash
# ==============================================================================
# Build script for PhysioRehab Clinic SaaS Deployment
# Target: Render, Railway, Fly.io, or Linux Container
# ==============================================================================
set -o errexit

echo "==> [1/4] Installing / verifying application dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "==> [2/4] Performing Django configuration validation..."
python manage.py check --settings=myproject.settings.production

echo "==> [3/4] Collecting static files via WhiteNoise..."
python manage.py collectstatic --no-input --settings=myproject.settings.production

echo "==> [4/4] Applying database migrations..."
python manage.py migrate --no-input --settings=myproject.settings.production

echo "==> Build preparation completed successfully."
