#!/bin/sh
set -eu

wait_for_database() {
  python - <<'PY'
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "betatrax.settings")

import django
from django.db import connection

django.setup()

timeout = int(os.getenv("DATABASE_WAIT_TIMEOUT", "60"))
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        connection.ensure_connection()
        connection.close()
        print("Database connection is ready.")
        sys.exit(0)
    except Exception as exc:
        last_error = exc
        print(f"Waiting for database: {exc}", flush=True)
        time.sleep(2)

print(f"Database was not ready after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

flag_enabled() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if flag_enabled "${AUTO_MIGRATE:-True}"; then
  wait_for_database

  if flag_enabled "${ENABLE_DJANGO_TENANTS:-False}"; then
    echo "Applying shared django-tenants migrations..."
    python manage.py migrate_schemas --shared --noinput
  else
    echo "Applying Django migrations..."
    python manage.py migrate --noinput
  fi
else
  echo "AUTO_MIGRATE is disabled; skipping database migrations."
fi

exec "$@"
