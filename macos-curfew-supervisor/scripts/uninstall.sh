#!/bin/bash
set -euo pipefail

DAEMON_PLIST="/Library/LaunchDaemons/com.example.curfewsupervisor.daemon.plist"

launchctl bootout system/com.example.curfewsupervisor.daemon >/dev/null 2>&1 || true
rm -f "$DAEMON_PLIST"

echo "Daemon removed."
echo "Per-user agents must be removed in each user session with:"
echo "  AGENT_PLIST=\"\$HOME/Library/LaunchAgents/com.example.curfewsupervisor.agent.plist\""
echo "  launchctl bootout gui/\$(id -u) com.example.curfewsupervisor.agent >/dev/null 2>&1 || true"
echo "  rm -f \"\$AGENT_PLIST\""
