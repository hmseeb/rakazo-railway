#!/usr/bin/env bash
# Version-pin test: every place that names the upstream release or our wrapper
# tag must agree, and the image itself must contain that upstream release.
# Usage: test/version.sh [upstream-version] [wrapper-tag]
#   e.g. test/version.sh v0.16.0 v0.16.0-r1
# Pass SKIP_IMAGE=1 to check the files only (no docker).
set -uo pipefail
cd "$(dirname "$0")/.."

UP="${1:-v0.16.0}"
TAG="${2:-v0.16.0-r1}"
REF="ghcr.io/hmseeb/rakazo-railway/app:$TAG"
fail=0
check() { # check DESCRIPTION COMMAND...
  if "${@:2}" >/dev/null 2>&1; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi
}

check "Dockerfile FROM upstream $UP" grep -qx "FROM ghcr.io/elie222/rakazo/app:$UP" image/Dockerfile
check "workflow TAG $TAG" grep -qE "^  TAG: $TAG\$" .github/workflows/build.yml
check "contract default image $TAG" grep -qF "IMAGE=\"\${1:-$REF}\"" test/contract.sh
check "template.json image.ref $TAG" python3 -c "import json,sys; d=json.load(open('template.json')); sys.exit(d['image']['ref']!='$REF')"
check "template.json service image $TAG" python3 -c "import json,sys; d=json.load(open('template.json')); sys.exit(not any(s.get('image')=='$REF' for s in d['services']))"
check "template.json upstream.version $UP" python3 -c "import json,sys; d=json.load(open('template.json')); sys.exit(not d['upstream']['version'].startswith('$UP '))"
check "TEMPLATE_OVERVIEW pins $TAG" grep -qF "(\`$TAG\`)" TEMPLATE_OVERVIEW.md
check "README names upstream $UP" grep -qF "app:$UP\`" README.md
check "no stale v0.13.0 mention" bash -c '! grep -rn "v0\.13\.0" image .github README.md TEMPLATE_OVERVIEW.md test/contract.sh'

if [ -z "${SKIP_IMAGE:-}" ]; then
  ver="${UP#v}"
  check "image $REF ships upstream CHANGELOG $ver" \
    docker run --rm --platform linux/amd64 --entrypoint bash "$REF" -c \
    "grep -m1 '^## \[[0-9]' /app/CHANGELOG.md | grep -qF '## [$ver]'"
fi

[ "$fail" = 0 ] && echo "PASS: $UP / $TAG" || { echo "FAILED"; exit 1; }
