#!/bin/bash
set -euo pipefail

DAEMON_PLIST="/Library/LaunchDaemons/com.example.curfewsupervisor.daemon.plist"

launchctl unload "$DAEMON_PLIST" >/dev/null 2>&1 || true
rm -f "$DAEMON_PLIST"

echo "Daemon removed."
echo "Per-user agents must be removed from each user's ~/Library/LaunchAgents manually."
