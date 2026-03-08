#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "Starting deployment..."

echo "1) Pulling latest code from Git..."
git pull --ff-only origin main

echo "2) Activating virtual environment..."
if [ -f ".nexusenv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .nexusenv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Warning: no local virtual environment found (.nexusenv or .venv)."
fi

echo "3) Installing dependencies..."
pip install -r requirements.txt

echo "4) Verifying model changes have migrations..."
python manage.py makemigrations --check --dry-run

echo "5) Applying database migrations..."
python manage.py migrate --noinput

echo "6) Ensuring no unapplied campus_nexus migrations remain..."
if python manage.py showmigrations campus_nexus | grep -q '\[ \]'; then
  echo "Error: unapplied campus_nexus migrations detected after migrate."
  exit 1
fi

echo "7) Collecting static files..."
python manage.py collectstatic --noinput

echo "8) Restarting app..."
mkdir -p tmp
touch tmp/restart.txt

echo "Deployment complete."
