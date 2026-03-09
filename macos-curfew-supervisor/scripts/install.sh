#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: sudo $0 /absolute/path/to/macos-curfew-supervisor"
  exit 1
fi

PROJECT_ROOT="$1"
if [ ! -d "$PROJECT_ROOT" ]; then
  echo "Project root not found: $PROJECT_ROOT"
  exit 1
fi

mkdir -p /var/log/macos-curfew-supervisor
mkdir -p /var/run/macos-curfew-supervisor/warnings
mkdir -p /var/db/macos-curfew-supervisor
mkdir -p /etc/macos-curfew-supervisor

if [ ! -f "$PROJECT_ROOT/config/supervisor.toml" ]; then
  cp "$PROJECT_ROOT/config/supervisor.example.toml" "$PROJECT_ROOT/config/supervisor.toml"
  echo "Created $PROJECT_ROOT/config/supervisor.toml (edit before production use)."
fi

if [ ! -f /etc/macos-curfew-supervisor/secret.key ]; then
  echo "changeme-supervisor-secret" >/etc/macos-curfew-supervisor/secret.key
fi
chmod 600 /etc/macos-curfew-supervisor/secret.key

DAEMON_PLIST_SRC="$PROJECT_ROOT/launchd/com.example.curfewsupervisor.daemon.plist"
DAEMON_PLIST_DST="/Library/LaunchDaemons/com.example.curfewsupervisor.daemon.plist"

sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" "$DAEMON_PLIST_SRC" >"$DAEMON_PLIST_DST"
chown root:wheel "$DAEMON_PLIST_DST"
chmod 644 "$DAEMON_PLIST_DST"

launchctl unload "$DAEMON_PLIST_DST" >/dev/null 2>&1 || true
launchctl load "$DAEMON_PLIST_DST"

echo "Daemon installed."
echo "For each standard user, install the agent plist in their ~/Library/LaunchAgents using the template in launchd/."
