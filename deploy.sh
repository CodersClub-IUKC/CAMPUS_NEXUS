#!/bin/bash
cd ~/your_project_directory

echo "🚀 Starting deployment..."

echo "1️⃣ Pulling latest code from GitHub..."
git pull origin main

echo "2️⃣ Activating virtual environment..."
source .nexusenv/bin/activate

echo "3️⃣ Installing dependencies..."
pip install -r requirements.txt

echo "4️⃣ Running migrations..."
python manage.py migrate --noinput

echo "5️⃣ Collecting static files..."
python manage.py collectstatic --noinput

echo "6️⃣ Restarting app..."
touch tmp/restart.txt   # Passenger restart signal

echo "✅ Deployment complete!"
