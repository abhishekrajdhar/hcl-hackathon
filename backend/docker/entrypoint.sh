#!/usr/bin/env bash
# Waits for Postgres, applies migrations, seeds the admin, then execs the CMD.
set -euo pipefail

HOST="${POSTGRES_HOST:-postgres}"
PORT="${POSTGRES_PORT:-5432}"
ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"

echo "[entrypoint] waiting for postgres at ${HOST}:${PORT}"
for i in $(seq 1 "${ATTEMPTS}"); do
  if python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${HOST}', ${PORT}))
except OSError:
    sys.exit(1)
finally:
    s.close()
" 2>/dev/null; then
    echo "[entrypoint] postgres is accepting connections"
    break
  fi
  if [ "${i}" -eq "${ATTEMPTS}" ]; then
    echo "[entrypoint] postgres did not become ready in time" >&2
    exit 1
  fi
  sleep 1
done

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying migrations"
  alembic upgrade head
fi

if [ "${RUN_SEED:-true}" = "true" ]; then
  echo "[entrypoint] seeding bootstrap data"
  python -m app.db.seed
fi

echo "[entrypoint] starting: $*"
exec "$@"
