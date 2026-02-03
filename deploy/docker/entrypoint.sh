#!/bin/sh
set -e

# Ensure database survives container restarts via /data volume
if [ -d /data ]; then
  # Try to take ownership (may fail on some storage classes, that's fine)
  chown -R 10001:10001 /data 2>/dev/null || true

  # If DB exists in image but not in /data, move it out to /data
  if [ -f /app/streamlit_app/okr_database.db ] && [ ! -f /data/okr_database.db ]; then
    echo "Moving bundled DB to /data for persistence"
    mv /app/streamlit_app/okr_database.db /data/okr_database.db
  fi
  # Create a symlink back to the app folder if not present
  if [ ! -e /app/streamlit_app/okr_database.db ] && [ -f /data/okr_database.db ]; then
    ln -s /data/okr_database.db /app/streamlit_app/okr_database.db || true
  fi
fi

exec "$@"
