#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: sudo $0 /absolute/path/to/macos-curfew-supervisor"
  exit 1
fi

PROJECT_ROOT="$1"
if [[ "$PROJECT_ROOT" != /* ]]; then
  echo "Project root must be an absolute path: $PROJECT_ROOT"
  exit 1
fi
if [ ! -d "$PROJECT_ROOT" ]; then
  echo "Project root not found: $PROJECT_ROOT"
  exit 1
fi

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "python3 not found in PATH"
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

sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" "$DAEMON_PLIST_SRC" >"$DAEMON_PLIST_DST"
chown root:wheel "$DAEMON_PLIST_DST"
chmod 644 "$DAEMON_PLIST_DST"

launchctl bootout system/com.example.curfewsupervisor.daemon >/dev/null 2>&1 || true
launchctl bootstrap system "$DAEMON_PLIST_DST"

echo "Daemon installed."
echo "Python interpreter: $PYTHON_BIN"
echo "For each standard user, install the agent plist with:"
echo "  AGENT_DST=\"\$HOME/Library/LaunchAgents/com.example.curfewsupervisor.agent.plist\""
echo "  sed -e 's|__PROJECT_ROOT__|$PROJECT_ROOT|g' -e 's|__PYTHON_BIN__|$PYTHON_BIN|g' \"$PROJECT_ROOT/launchd/com.example.curfewsupervisor.agent.plist\" > \"\$AGENT_DST\""
echo "  launchctl bootout gui/\$(id -u) com.example.curfewsupervisor.agent >/dev/null 2>&1 || true"
echo "  launchctl bootstrap gui/\$(id -u) \"\$AGENT_DST\""
