#!/usr/bin/env bash
# Rakazo boot on Railway. Runs as root only long enough to fix volume ownership.
set -uo pipefail

# Railway volume mounts are root-owned; the app writes DATA_DIR as node.
chown -R node:node /data

# Drop to node and run the stack. First process to exit takes the container
# down with it so Railway's restart policy replaces the whole unit instead of
# leaving a half-dead stack serving 502s.
exec runuser -u node -- bash -c '
set -u
cd /app
pnpm --filter @rakazo/db exec prisma migrate deploy || exit 1
pnpm --filter @rakazo/api start & p1=$!
pnpm --filter @rakazo/worker start & p2=$!
pnpm --filter @rakazo/web preview --host :: --port "${PORT:-5173}" & p3=$!
wait -n "$p1" "$p2" "$p3"
kill "$p1" "$p2" "$p3" 2>/dev/null
exit 1
'
