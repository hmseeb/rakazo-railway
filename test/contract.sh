#!/usr/bin/env bash
# Contract test for ghcr.io/hmseeb/rakazo-railway. Fails if the wrapper image
# stops doing the two things it exists for: booting the whole stack as node on
# a root-owned volume, and serving the app through the vite preview proxy.
# Usage: test/contract.sh [image-ref]
set -uo pipefail

IMAGE="${1:-ghcr.io/hmseeb/rakazo-railway/app:v0.16.0-r1}"
NET="rakazo-contract-$$"
PG="rakazo-pg-$$"
APP="rakazo-app-$$"
PGPASS="contractpw$$"
OWNER_PW="contract-owner-pw-$$-0123456789"

cleanup() {
  docker rm -f "$APP" "$PG" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
}
trap cleanup EXIT
fail() { echo "FAIL: $1"; exit 1; }

docker rm -f "$APP" "$PG" >/dev/null 2>&1
docker network rm "$NET" >/dev/null 2>&1
docker volume rm "rakazo-data-$$" >/dev/null 2>&1

docker network create "$NET" >/dev/null || fail "docker network"

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_PASSWORD="$PGPASS" -e POSTGRES_DB=rakazo \
  postgres:16-alpine >/dev/null || fail "postgres start"
for _ in $(seq 1 30); do docker exec "$PG" pg_isready -U postgres -d rakazo >/dev/null 2>&1 \
  && docker exec "$PG" psql -U postgres -d rakazo -tAc "select 1" >/dev/null 2>&1 && break; sleep 1; done

# Anonymous pullability is itself part of the contract: Railway pulls without
# credentials, so this must work in a logged-out registry context too.
# CI tests the freshly built image before pushing it, so a local image is used as is.
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE" >/dev/null || fail "image pull $IMAGE"

# Named volume, never chowned by us: docker creates it root-owned, matching
# Railway's volume mounts.
HOST_PORT="${HOST_PORT:-15173}"
docker run -d --name "$APP" --network "$NET" -p 127.0.0.1:$HOST_PORT:5173 \
  -v "rakazo-data-$$:/data" \
  -e NODE_ENV=production \
  -e DATABASE_URL="postgresql://postgres:$PGPASS@$PG:5432/rakazo" \
  -e BETTER_AUTH_SECRET=contract-test-secret-0123456789abcdef \
  -e BETTER_AUTH_URL=http://127.0.0.1:5173 \
  -e WEB_ORIGIN=http://127.0.0.1:5173 \
  -e API_URL=http://127.0.0.1:5173 \
  -e RAKAZO_HOST=127.0.0.1 \
  -e ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -e SCREEN_PROXY_SECRET=contract-screen-secret-0123456789ab \
  -e SIGNUPS_ENABLED=false \
  -e OWNER_EMAIL=owner@contract.test \
  -e OWNER_PASSWORD="$OWNER_PW" \
  -e SANDBOX_PROVIDER=none \
  -e DATA_DIR=/data \
  "$IMAGE" >/dev/null || fail "app start"

# 1. Serves the app through the vite proxy (proves web + proxy + api + migrate).
ok=""
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$HOST_PORT/api/auth/capabilities || true)
  [ "$code" = "200" ] && { ok=1; break; }
  docker ps -q -f name="$APP" | grep -q . || { docker logs "$APP" 2>&1 | tail -30; fail "container exited before becoming healthy"; }
  sleep 2
done
[ -n "$ok" ] || { docker logs "$APP" 2>&1 | tail -30; fail "/api/auth/capabilities never returned 200"; }

# 2. IPv6: Railway dials containers over v6, so the listener must cover it.
docker exec "$APP" node -e 'fetch("http://[::1]:5173/api/auth/capabilities").then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))' \
  || fail "not listening on IPv6 (::)"

# 3. node can write the (root-owned-at-mount) volume.
docker exec -u node "$APP" touch /data/.contract-write-test \
  || fail "uid 1000 cannot write /data (volume chown missing)"

# 4. All three processes alive.
# /proc, not ps: the upstream slim base ships without procps.
procs=$(docker exec "$APP" bash -c 'for f in /proc/[0-9]*/cmdline; do tr "\\0" " " < "$f" 2>/dev/null; echo; done | grep -c "^pnpm --filter @rakazo/\(api\|worker\|web\) "')
[ "$procs" -ge 3 ] || fail "expected api+worker+web running, found $procs"

# 5. Railway's healthchecker sends Host: healthcheck.railway.app. vite preview
# must answer it or every deploy dies at healthcheck, while other unknown Hosts
# stay blocked (no wildcard allowedHosts).
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: healthcheck.railway.app' http://127.0.0.1:$HOST_PORT/api/auth/capabilities)
[ "$code" = "200" ] || fail "healthcheck Host got $code (RAKAZO_ALLOWED_HOSTS missing)"
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: probe.invalid' http://127.0.0.1:$HOST_PORT/api/auth/capabilities)
[ "$code" = "403" ] || fail "unknown Host got $code, expected 403"

# 6. Migration actually ran.
docker exec "$PG" psql -U postgres -d rakazo -tAc "select count(*) from information_schema.tables where table_schema='public'" \
  | awk '$1 > 5 {ok=1} END {exit ok?0:1}' || fail "prisma migrate deploy did not create the schema"

auth() { # auth PATH JSON -> http code
  curl -s -o /dev/null -w '%{http_code}' -H 'Origin: http://127.0.0.1:5173' -H 'Content-Type: application/json' \
    -d "$2" "http://127.0.0.1:$HOST_PORT/api/auth/$1"
}
owner_signin() { auth sign-in/email "{\"email\":\"owner@contract.test\",\"password\":\"$OWNER_PW\"}"; }

# 6b. Who can sign up: the boot bootstraps OWNER_EMAIL, and a stranger is refused.
code=$(owner_signin); [ "$code" = "200" ] || fail "owner sign-in got $code (OWNER_EMAIL bootstrap missing)"
code=$(auth sign-up/email '{"email":"stranger@contract.test","password":"stranger-pw-0123456789","name":"x"}')
[ "$code" != "200" ] || fail "stranger sign-up accepted (signups must be closed)"

# 7. Boot is idempotent: Railway restarts keep the container filesystem.
for n in 2 3; do
  docker restart "$APP" >/dev/null || fail "restart $n"
  ok=""
  for _ in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$HOST_PORT/api/auth/capabilities || true)
    [ "$code" = "200" ] && { ok=1; break; }
    sleep 2
  done
  [ -n "$ok" ] || { docker logs "$APP" 2>&1 | tail -30; fail "not healthy after start $n"; }
  code=$(owner_signin); [ "$code" = "200" ] || fail "owner sign-in got $code after start $n"
done

docker volume rm "rakazo-data-$$" >/dev/null 2>&1
echo "PASS: $IMAGE"
