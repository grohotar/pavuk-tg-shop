#!/bin/bash
# Before a prod release: show exactly what will reach prod and refuse if sandbox-only things leaked out of sandbox/.
#   sandbox/release-check.sh            compare HEAD with the latest prod-* tag
#   sandbox/release-check.sh <tag>      compare with a given tag
# Prod runs branch remnawave-3-compat in /root/pavuk-tg-shop on the panel server (84.21.189.111).
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${1:-$(git tag -l 'prod-*' --sort=-creatordate | head -1)}
[ -z "$(git status --porcelain)" ] || { echo "STOP: uncommitted changes"; git status --short; exit 1; }
[ "$(git branch --show-current)" = remnawave-3-compat ] || { echo "STOP: not on remnawave-3-compat"; exit 1; }
echo "== prod tag: $BASE   HEAD: $(git rev-parse --short HEAD)"
echo "== commits going to prod:"; git log --oneline "$BASE"..HEAD
echo "== files going to prod (sandbox/ excluded, it is in .dockerignore):"
git diff --stat "$BASE"..HEAD -- . ':!sandbox'
LEAK=$(git diff "$BASE"..HEAD -- . ':!sandbox' | grep -E '^\+' | grep -iE 'na4u|ppntestbot|sandbox-local|127\.0\.0\.1:3999|sub\.sandbox\.invalid' \
  | grep -vE 'pipun_(icons|accent)_by_ppntestbot' || true)  # emoji sets used in prod, created by the test bot
[ -z "$LEAK" ] || { echo "STOP: sandbox-only values outside sandbox/:"; echo "$LEAK"; exit 1; }
grep -qx 'sandbox/' .dockerignore || { echo "STOP: sandbox/ missing from .dockerignore"; exit 1; }
cat <<'TXT'
== OK. Also before release:
  - prod .env: decide which sandbox settings (sandbox/README.md, "Отличия .env") are turned on in prod
  - prod-only hooks must stay inert: BOT_POLLING and PLATEGA_API_BASE_URL are NOT set in prod .env
  - after release: git tag prod-YYYY-MM-DD <deployed commit>
TXT
