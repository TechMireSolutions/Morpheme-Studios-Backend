#!/usr/bin/env bash
# deploy.sh
# Automated deployment script for Morpheme Studios.
# Run this from the server.

set -e

BACKEND_DIR="/srv/morpheme/backend"
FRONTEND_DIR="/srv/morpheme/frontend"

echo "=========================================="
echo "Starting Deployment..."
echo "=========================================="

echo "=> 1. Deploying Backend..."
cd $BACKEND_DIR
git pull origin main

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip
pip install -r requirements/prod.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "=> 2. Deploying Frontend (SSG)..."
cd $FRONTEND_DIR
git pull origin main

npm ci
npm run build

echo "=> 3. Restarting Services..."
# The user needs passwordless sudo for systemctl or to run this as root
sudo systemctl restart morpheme
sudo systemctl restart celery || true

echo "=========================================="
echo "Deployment Complete! 🚀"
echo "=========================================="
