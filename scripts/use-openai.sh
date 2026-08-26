#!/usr/bin/env bash
# Switch the stack to OpenAI for both the LLM and the embeddings.
# Reads the key from your environment; it is never written to a tracked file.
set -euo pipefail
: "${OPENAI_API_KEY:?export OPENAI_API_KEY first}"
cd "$(dirname "$0")"

ENV=backend/.env
touch "$ENV"
python3 - "$ENV" <<'PY'
import re, sys
path = sys.argv[1]
lines = open(path).read().splitlines()
want = {"LLM_PROVIDER": "openai", "EMBEDDING_PROVIDER": "openai"}
seen = set()
out = []
for line in lines:
    m = re.match(r"\s*([A-Z_]+)\s*=", line)
    key = m.group(1) if m else None
    if key in want:
        out.append(f"{key}={want[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, val in want.items():
    if key not in seen:
        out.append(f"{key}={val}")
open(path, "w").write("\n".join(out) + "\n")
print("backend/.env updated: LLM_PROVIDER=openai, EMBEDDING_PROVIDER=openai")
PY

# The key goes in via the environment, so it never lands in a tracked file.
docker compose up -d --force-recreate api >/dev/null
for _ in $(seq 1 40); do curl -sf -m 2 http://localhost:8000/health >/dev/null && break; sleep 1; done

echo "re-embedding the catalogue with the new vectors…"
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${FIRST_ADMIN_EMAIL:-admin@example.com}\",\"password\":\"${FIRST_ADMIN_PASSWORD:-admin12345}\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl -s -X POST "http://localhost:8000/api/v1/resources/embed-all?only_missing=false" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
