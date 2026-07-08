#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
VIRTUALENV="${VIRTUALENV:-/home/codemsdx/virtualenv/campusnexus.codersug.com/3.12}"
BRANCH="${BRANCH:-main}"
DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-core.settings.production}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-https://campusnexus.codersug.com/api/health/}"
RUN_HEALTH_CHECK="${RUN_HEALTH_CHECK:-true}"

cd "$PROJECT_DIR"
export DJANGO_SETTINGS_MODULE

echo "Starting deployment..."
echo "Project directory: $PROJECT_DIR"
echo "Django settings: $DJANGO_SETTINGS_MODULE"

echo "1) Checking Git working tree..."
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: working tree has uncommitted changes. Resolve them before deploying."
  git status --short
  exit 1
fi

echo "2) Activating virtual environment..."
if [ -f "$VIRTUALENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VIRTUALENV/bin/activate"
elif [ -f ".nexusenv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .nexusenv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Warning: no local virtual environment found (.nexusenv or .venv)."
fi

echo "3) Pulling latest code from Git..."
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "4) Installing dependencies..."
pip install -r requirements.txt

echo "5) Running Django checks..."
python manage.py check
python manage.py check --deploy

echo "6) Verifying model changes have migrations..."
python manage.py makemigrations --check --dry-run

echo "7) Applying database migrations..."
python manage.py migrate --noinput

echo "8) Ensuring no unapplied campus_nexus migrations remain..."
if python manage.py showmigrations campus_nexus | grep -q '\[ \]'; then
  echo "Error: unapplied campus_nexus migrations detected after migrate."
  exit 1
fi

echo "9) Collecting static files..."
python manage.py collectstatic --noinput

echo "10) Restarting Passenger app..."
mkdir -p tmp
touch tmp/restart.txt

if [ "$RUN_HEALTH_CHECK" = "true" ]; then
  echo "11) Checking health endpoint..."
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error "$HEALTH_CHECK_URL" >/dev/null
  else
    python -c "import urllib.request; urllib.request.urlopen('$HEALTH_CHECK_URL', timeout=10).read()"
  fi
fi

echo "Deployment complete."
