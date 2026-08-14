#!/bin/zsh
set -euo pipefail

LABEL="com.pete.ebay-seller-local"
ROOT="${0:A:h:h}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"
DOMAIN="gui/$(id -u)"

mkdir -p "${PLIST:h}" "$LOG_DIR"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

cat >"$tmp" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/scripts/run_local_http_service.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/ebay-seller-local.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/ebay-seller-local.err.log</string>
</dict>
</plist>
EOF

plutil -lint "$tmp"
cp "$tmp" "$PLIST"

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
  for _ in {1..20}; do
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || break
    sleep 0.25
  done
fi

if ! launchctl bootstrap "$DOMAIN" "$PLIST"; then
  sleep 1
  launchctl bootstrap "$DOMAIN" "$PLIST"
fi
launchctl kickstart -k "$DOMAIN/$LABEL"

print "Installed and started $LABEL."
