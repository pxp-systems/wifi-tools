# macOS Curfew Supervisor

Production-leaning MVP for per-user curfew enforcement on macOS.

## What it does

- Enforces curfew for **standard users only** (non-admin)
- Ignores admin accounts entirely
- Uses **Pacific/Auckland** local civil time
- Base curfew: **22:30** daily
- Warning moments: **22:15, 22:20, 22:28**
- Opens per-user localhost warning page
- Valid override code grants **+30 minutes** for that user only
- If a user is logged out after missing curfew, re-login is blocked for that NZ day unless override is entered during short grace
- Performs **targeted user logout**, not machine shutdown
- Sends outbound Telegram supervisory notifications

## Architecture

Two cooperating components:

1. **Privileged LaunchDaemon** (`daemon.main`)
   - Source of truth for policy and state
   - Detects logged-in users and admin membership
   - Manages per-user deadlines and warnings
   - Validates overrides (server-side)
   - Performs targeted logout for standard users
   - Sends Telegram notifications

2. **Per-user LaunchAgent** (`agent.main`)
   - Polls daemon for pending warning events for its own user
   - Opens warning page in browser (`http://127.0.0.1:8765/warning?token=...`)
   - Optionally shows native notifications

## Override code algorithm

Deterministic and independently reproducible.

Message format:

```text
YYYY-MM-DD:HH:username
```

Where date/hour are from `Pacific/Auckland`.

Code derivation:

- `digest = HMAC-SHA256(secret, message)`
- Base32 encode digest, remove confusing chars (`I`, `L`, `O`, `0`, `1`)
- Take first 5 chars as code

Validation uses constant-time compare.

Standalone generator:

```bash
python -m security.codegen --config config/supervisor.toml --user alice
```

## Config

Copy and edit:

```bash
cp config/supervisor.example.toml config/supervisor.toml
```

Put your secret in a root-readable file (not world-readable), then point `secret_file` at it.

`relogin_grace_seconds` controls the post-relogin window (default 60s) before re-logout for blocked users.

## Local dev

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

Run daemon (foreground):

```bash
python -m daemon.main --config config/supervisor.toml
```

Run agent in another terminal (as current user):

```bash
python -m agent.main --config config/supervisor.toml
```

## Install (launchd)

```bash
chmod +x scripts/install.sh
sudo scripts/install.sh /absolute/path/to/macos-curfew-supervisor
```

Then, for each standard user (run as that user, not root):

```bash
PROJECT_ROOT=/absolute/path/to/macos-curfew-supervisor
PYTHON_BIN="$(command -v python3.11 || command -v python3)"
AGENT_DST="$HOME/Library/LaunchAgents/com.example.curfewsupervisor.agent.plist"

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" \
  "$PROJECT_ROOT/launchd/com.example.curfewsupervisor.agent.plist" > "$AGENT_DST"

launchctl bootout gui/$(id -u) com.example.curfewsupervisor.agent >/dev/null 2>&1 || true
launchctl bootstrap gui/$(id -u) "$AGENT_DST"
```

## Update after pulling latest changes

```bash
git pull
sudo scripts/install.sh /absolute/path/to/macos-curfew-supervisor
```

Re-run the agent install block above for each standard user.

Uninstall:

```bash
chmod +x scripts/uninstall.sh
sudo scripts/uninstall.sh
```

## Security notes

- Secret key never leaves daemon process.
- UI never receives secret; submits only override code + warning token.
- Override tokens are random and user-bound.
- State DB and logs should be writable only by root.
- This is an MVP: harden transport/auth further for high-assurance environments.

## Known limitations

- Localhost web endpoints are not user-authenticated beyond warning token binding.
- Admin detection depends on `dsmemberutil` behavior.
- Targeted logout uses `launchctl bootout gui/<uid>` with a kill fallback.
- Telegram inbound command handling is not included in this phase.
