#!/usr/bin/env bash
# Rakazo boot on Railway. Runs as root only long enough to fix volume ownership.
set -uo pipefail

# Railway volume mounts are root-owned; the app writes DATA_DIR as node.
chown -R node:node /data

# vite preview only answers requests whose Host header is RAKAZO_HOST
# (allowedHosts: [previewHost] in apps/web/vite.config.ts). Railway's
# healthchecker dials the container directly and sends an internal Host, so
# every probe got 403 'Blocked request' and the deploy died at healthcheck
# while the app was healthy (verified live 2026-09-10). The edge keeps sending
# the real public Host, and the api is loopback-only behind the proxy, so
# turning the check off exposes nothing that was not already public.
VITE_CONFIG=/app/apps/web/vite.config.ts
if grep -q 'allowedHosts: \[previewHost\]' "$VITE_CONFIG"; then
  sed -i 's/allowedHosts: \[previewHost\]/allowedHosts: true/' "$VITE_CONFIG"
  chmod 644 "$VITE_CONFIG"
else
  echo "rakazo-boot: WARN expected allowedHosts line not found in $VITE_CONFIG; upstream changed it?" >&2
fi

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
