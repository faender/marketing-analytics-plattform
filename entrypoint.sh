#!/usr/bin/env bash
set -e

python << 'PYEOF'
import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from django.db import connections
from django.db.utils import OperationalError

conn = connections["default"]
for attempt in range(1, 31):
    try:
        conn.cursor()
        print("Database is available.")
        break
    except OperationalError:
        print(f"Database not ready (attempt {attempt}/30) - retrying in 1s...")
        time.sleep(1)
else:
    raise SystemExit("Database never became available.")
PYEOF

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8000
