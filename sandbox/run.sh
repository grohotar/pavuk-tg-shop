#!/bin/bash
# Sandbox. Nothing here talks to the real panel, payment systems or VPN servers.
#   sandbox/run.sh           bot on this Mac (polling); fake panel + mini app on netangels (ppn-panel / ppn .na4u.ru)
#   sandbox/run.sh seed      recreate test data (local DB + panel_state.json on netangels)
#   sandbox/run.sh deploy    rebuild mini app, upload mini app + fake panel to netangels
#   sandbox/run.sh local     everything on this Mac, mini app in the browser: http://127.0.0.1:3999/frame
#   sandbox/run.sh build     rebuild the mini app only
set -e
cd "$(dirname "$0")/.."
BOT_DIR=$PWD
APP_DIR=$BOT_DIR/../miniapp-sandbox
NODE18=$BOT_DIR/../.tools/node-v18.20.8-darwin-arm64/bin
PG=/opt/homebrew/opt/postgresql@17/bin
export PATH=$NODE18:$PATH NEXT_TELEMETRY_DISABLED=1

brew services start postgresql@17 >/dev/null 2>&1 || true
until $PG/pg_isready -q -h 127.0.0.1; do sleep 0.5; done
$PG/psql -h 127.0.0.1 -d postgres -tAc "select 1 from pg_roles where rolname='sandbox'" | grep -q 1 \
  || $PG/psql -h 127.0.0.1 -d postgres -c "create role sandbox login password 'sandbox' createdb"
$PG/psql -h 127.0.0.1 -d postgres -tAc "select 1 from pg_database where datname='tgshop_sandbox'" | grep -q 1 \
  || $PG/createdb -h 127.0.0.1 -O sandbox tgshop_sandbox
[ -d .venv ] || { /opt/homebrew/bin/python3.11 -m venv .venv; .venv/bin/pip install -q -r sandbox/prod-requirements.lock; }

case "${1:-}" in
  seed)   .venv/bin/python sandbox/seed.py && sandbox/deploy.sh state; exit ;;
  build)  # same steps as the mini app Dockerfile (pnpm 10.11.0, frozen lockfile, next build, standalone)
          command -v pnpm >/dev/null || npm i -g -s pnpm@10.11.0
          cp "$APP_DIR/sandbox/prod-app-config.json" "$APP_DIR/public/assets/app-config.json"  # prod mounts it
          cd "$APP_DIR" && pnpm install --frozen-lockfile && pnpm run build; exit ;;
  deploy) "$0" build && sandbox/deploy.sh; exit ;;
  local)
    [ -f "$APP_DIR/.next/standalone/server.js" ] || "$0" build
    PIDS=(); trap 'kill ${PIDS[@]} 2>/dev/null' EXIT
    node sandbox/fake-panel.js > sandbox/fake_panel.log 2>&1 & PIDS+=($!)
    (cd "$APP_DIR" && rm -rf .next/standalone/public .next/standalone/.next/static \
      && cp -R public .next/standalone/ && cp -R .next/static .next/standalone/.next/ && cd .next/standalone && \
      TELEGRAM_BOT_TOKEN=sandbox-local REMNAWAVE_PANEL_URL=http://127.0.0.1:3999 REMNAWAVE_TOKEN=x \
      BUY_LINK=https://t.me/ppntestbot/start CRYPTO_LINK= REDIRECT_LINK="https://redirect.pavuka.net/?redirect_to=" \
      NODE_ENV=production PORT=3020 HOSTNAME=127.0.0.1 exec node server.js) > sandbox/miniapp.log 2>&1 & PIDS+=($!)
    echo "Mini app: http://127.0.0.1:3999/frame   (bot not started in local mode)"
    wait; exit ;;
esac

[ -f sandbox/panel_state.json ] || "$0" seed
exec .venv/bin/python main.py
