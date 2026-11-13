#!/bin/bash
# Upload the sandbox mini app and fake panel to netangels (ppn.na4u.ru, ppn-panel.na4u.ru).
# Touches only these two sites (their app/ dir). Run from anywhere:
#   sandbox/deploy.sh          build mini app if needed, upload both, restart
#   sandbox/deploy.sh state    upload only panel_state.json (after seed.py)
set -euo pipefail
cd "$(dirname "$0")/.."
BOT_DIR=$PWD
APP_DIR=$BOT_DIR/../miniapp-sandbox
NODE18=$BOT_DIR/../.tools/node-v18.20.8-darwin-arm64/bin
export PATH=$NODE18:$PATH NEXT_TELEMETRY_DISABLED=1
HOST=c61358@h35.netangels.ru
SSH=(ssh -i ~/.ssh/claude_ro -o IdentitiesOnly=yes -o BatchMode=yes "$HOST")
MINI=ppn.na4u.ru PANEL=ppn-panel.na4u.ru
env_get() { grep -E "^$1=" .env | cut -d= -f2-; }

KEY=$(env_get PANEL_API_KEY)
[ ${#KEY} -ge 32 ] || { echo "PANEL_API_KEY in .env must be a long random string"; exit 1; }

if [ "${1:-}" = state ]; then
  "${SSH[@]}" "cat > ~/$PANEL/app/panel_state.json.new && mv ~/$PANEL/app/panel_state.json.new ~/$PANEL/app/panel_state.json" < sandbox/panel_state.json
  echo "panel_state.json uploaded"; exit 0
fi

TOKEN=$(env_get BOT_TOKEN)
BOT_USER=$(curl -s "https://api.telegram.org/bot$TOKEN/getMe" | .venv/bin/python -c 'import json,sys;print(json.load(sys.stdin)["result"]["username"])')
PANEL_PORT=$("${SSH[@]}" "cat ~/$PANEL/etc/environment/APP_PORT")
PANEL_IP=$("${SSH[@]}" "cat ~/$PANEL/etc/environment/APP_IP")

# ---- fake panel ----
P=$(mktemp -d)
cp sandbox/fake-panel.js sandbox/subpage_configs.json sandbox/panel_state.json "$P/"
printf '%s' "$KEY" > "$P/panel.key"
cat > "$P/hello.js" <<EOF
// netangels starts app/hello.js. Sandbox fake panel, see bot-sandbox/sandbox/fake-panel.js
// netangels runs its own Node version; re-run this file under the prod version (v18.20.8) instead.
const NODE = require('os').homedir() + '/.nvm/versions/node/v18.20.8/bin/node'
if (process.version !== 'v18.20.8') {
  const c = require('child_process').spawn(NODE, [__filename], { stdio: 'inherit' })
  for (const sig of ['SIGTERM', 'SIGINT', 'SIGHUP']) process.on(sig, () => c.kill(sig))
  c.on('exit', (code, sig) => process.exit(code ?? (sig ? 1 : 0)))
  return
}
process.env.PANEL_KEY = require('fs').readFileSync(__dirname + '/panel.key', 'utf8').trim()
process.env.MINIAPP_URL = 'https://$MINI'
process.env.PUBLIC_URL = 'https://$PANEL'
require('./fake-panel.js').start()
EOF

# ---- mini app: prod Dockerfile layout (standalone + public + .next/static), sharp for linux-x64 ----
[ -f "$APP_DIR/.next/standalone/server.js" ] || "$BOT_DIR/sandbox/run.sh" build
M=$(mktemp -d)
cp -R "$APP_DIR/.next/standalone/." "$M/"
cp -R "$APP_DIR/public" "$M/" && mkdir -p "$M/.next" && cp -R "$APP_DIR/.next/static" "$M/.next/"
fetch_pkg() {  # name version integrity -> extracted into .pnpm store layout, verified against pnpm-lock
  local name=$1 ver=$2 dir="$M/node_modules/.pnpm/${1/\//+}@$2/node_modules/$1" tgz
  tgz=$(cd "$P" && npm pack -s "$name@$ver")
  local want; want=$(grep -A1 "^  '$name@$ver':" "$APP_DIR/pnpm-lock.yaml" | grep -oE 'sha512-[A-Za-z0-9+/=]+')
  local got="sha512-$(openssl dgst -sha512 -binary "$P/$tgz" | base64)"
  [ "$want" = "$got" ] || { echo "integrity mismatch for $name"; exit 1; }
  mkdir -p "$dir" && tar xzf "$P/$tgz" -C "$dir" --strip-components=1 && rm "$P/$tgz"
}
fetch_pkg @img/sharp-linux-x64 0.34.3
fetch_pkg @img/sharp-libvips-linux-x64 1.2.0
IMG="$M/node_modules/.pnpm/sharp@0.34.3/node_modules/@img"
rm -rf "$M"/node_modules/.pnpm/@img+sharp-*darwin* "$IMG"/sharp-*darwin*
ln -s ../../../@img+sharp-linux-x64@0.34.3/node_modules/@img/sharp-linux-x64 "$IMG/sharp-linux-x64"
ln -s ../../../@img+sharp-libvips-linux-x64@1.2.0/node_modules/@img/sharp-libvips-linux-x64 "$IMG/sharp-libvips-linux-x64"
printf 'TELEGRAM_BOT_TOKEN=%s,sandbox-local\nREMNAWAVE_TOKEN=%s\n' "$TOKEN" "$KEY" > "$M/sandbox.secrets"
cat > "$M/hello.js" <<EOF
// netangels starts app/hello.js. Same env as the prod container, values pointed at the sandbox.
// netangels runs its own Node version; re-run this file under the prod version (v18.20.8) instead.
const NODE = require('os').homedir() + '/.nvm/versions/node/v18.20.8/bin/node'
if (process.version !== 'v18.20.8') {
  const c = require('child_process').spawn(NODE, [__filename], { stdio: 'inherit' })
  for (const sig of ['SIGTERM', 'SIGINT', 'SIGHUP']) process.on(sig, () => c.kill(sig))
  c.on('exit', (code, sig) => process.exit(code ?? (sig ? 1 : 0)))
  return
}
const fs = require('fs')
for (const l of fs.readFileSync(__dirname + '/sandbox.secrets', 'utf8').split('\n')) {
  const i = l.indexOf('='); if (i > 0) process.env[l.slice(0, i)] = l.slice(i + 1)
}
Object.assign(process.env, {
  REMNAWAVE_PANEL_URL: 'http://$PANEL_IP:$PANEL_PORT', BUY_LINK: 'https://t.me/$BOT_USER/start', CRYPTO_LINK: '',
  REDIRECT_LINK: 'https://redirect.pavuka.net/?redirect_to=', NODE_ENV: 'production', NEXT_TELEMETRY_DISABLED: '1',
  PORT: process.env.APP_PORT, HOSTNAME: process.env.APP_IP,
})
require('./server.js')
EOF
chmod 600 "$P/panel.key" "$M/sandbox.secrets"

upload() {  # local_dir site
  COPYFILE_DISABLE=1 tar --no-xattrs -czf - -C "$1" . | "${SSH[@]}" "set -e; cd ~/$2; rm -rf app.new app.old; mkdir app.new; tar xzf - -C app.new; \
    mv app app.old; mv app.new app; rm -rf app.old; touch reload"
}
upload "$P" $PANEL
upload "$M" $MINI
rm -rf "$P" "$M"
echo "uploaded; check: https://$PANEL/frame?key=<PANEL_API_KEY>  and the bot @$BOT_USER"
