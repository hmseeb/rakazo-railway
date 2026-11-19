#!/usr/bin/env bash
# Rakazo boot on Railway. Runs as root only long enough to fix volume ownership.
set -uo pipefail

# Railway volume mounts are root-owned; the app writes DATA_DIR as node.
chown -R node:node /data

# vite preview only answers requests whose Host is RAKAZO_HOST or listed in
# RAKAZO_ALLOWED_HOSTS. Railway's healthchecker sends Host:
# healthcheck.railway.app, so without it every probe got 403 'Blocked request'
# and deploys died at healthcheck while the app was healthy. Upstream's own
# Railway image sets the same value. Env only: nothing in the image is patched,
# so in-place restarts (same filesystem) boot identically.
case ",${RAKAZO_ALLOWED_HOSTS:-}," in
  *,healthcheck.railway.app,*) ;;
  *) export RAKAZO_ALLOWED_HOSTS="healthcheck.railway.app${RAKAZO_ALLOWED_HOSTS:+,$RAKAZO_ALLOWED_HOSTS}" ;;
esac
# Same defaults as upstream infra/railway/start.sh: the api sits behind the
# loopback web proxy, and Railway's edge names the client in X-Real-IP.
export TRUSTED_PROXIES="${TRUSTED_PROXIES:-127.0.0.1}"
export CLIENT_IP_HEADER="${CLIENT_IP_HEADER:-x-real-ip}"

# Drop to node and run the stack. First process to exit takes the container
# down with it so Railway's restart policy replaces the whole unit instead of
# leaving a half-dead stack serving 502s.
exec runuser -u node -- bash -c '
set -u
cd /app
pnpm --filter @rakazo/api db:deploy || exit 1
pnpm --filter @rakazo/api start & p1=$!
pnpm --filter @rakazo/worker start & p2=$!
# The web server needs none of the api secrets (upstream drops the same set).
env -u DATABASE_URL -u ENCRYPTION_KEY -u BETTER_AUTH_SECRET \
  pnpm --filter @rakazo/web preview --host :: --port "${PORT:-5173}" & p3=$!
wait -n "$p1" "$p2" "$p3"
kill "$p1" "$p2" "$p3" 2>/dev/null
exit 1
'
