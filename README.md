# afterai-relay

Public-safe browser relay skill for agent automation.

`afterai-relay` launches a persistent local CDP browser and lets you switch between:

- **CloakBrowser** — stealth patched Chromium for automation-heavy pages.
- **BrowserOS** — Chromium-compatible browser path for GUI/MCP-style workflows.

It is designed to be copied into a Hermes skill directory or used standalone from a cloned repo.

## What this repo does not contain

- no cookies
- no API keys
- no private IPs or hostnames
- no hardcoded user accounts
- no browser profile data
- no downloaded browser binaries

## Install CloakBrowser path

```bash
scripts/install-cloakbrowser.sh
```

This creates:

```text
~/.local/share/afterai-relay/cloakbrowser-venv/
~/.local/bin/cloakbrowser-chrome
```

The wrapper injects CloakBrowser fingerprint flags before normal Chromium/CDP flags.

## Install BrowserOS path

Install BrowserOS using the official project instructions, then ensure `browseros` is on `PATH`.

Linux `.deb` example:

```bash
curl -fsSL "https://cdn.browseros.com/download/BrowserOS.deb" -o /tmp/browseros.deb
sudo dpkg -i /tmp/browseros.deb
sudo apt-get install -f -y
```

## Configuration

Copy the template if you want stable local settings:

```bash
cp templates/afterai-relay.env.example .env
```

Then edit `.env`. The script auto-loads `.env` from the repo root when present.

Key variables:

```text
AFTERAI_RELAY_BACKEND=auto|cloakbrowser|browseros|chromium
AFTERAI_RELAY_PORT=18800
AFTERAI_RELAY_HOST=127.0.0.1
AFTERAI_RELAY_PROFILE_DIR=~/.local/share/afterai-relay/profiles/default
AFTERAI_RELAY_DISPLAY=:1002
AFTERAI_RELAY_HEADLESS=0|1
CLOAKBROWSER_FINGERPRINT_PLATFORM=windows|macos
```

## Commands

```bash
scripts/afterai-relay doctor
scripts/afterai-relay status
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay launch --backend browseros
scripts/afterai-relay open https://example.com
scripts/afterai-relay tabs
scripts/afterai-relay health
scripts/afterai-relay kill
```

## Temporary interactive login

Use this when the user must personally enter a password, passkey, CAPTCHA, consent, or 2FA into the persistent Relay profile:

```bash
scripts/afterai-relay auth start --tunnel cloudflared --ttl 900 https://accounts.google.com/
scripts/afterai-relay auth status
scripts/afterai-relay auth stop
```

Security properties:

- x11vnc and noVNC listen on `127.0.0.1` only;
- the quick tunnel and VNC credential are short-lived;
- the credential is generated per run and omitted from state/status output;
- the session auto-expires after 5–60 minutes (15 minutes by default);
- stopping auth removes the VNC password file but keeps the persistent browser profile;
- never record, screenshot, or export credentials, cookies, or auth headers.

## Webwright-style task factory

`afterai-relay` creates durable browser task workspaces and now has the first reproducible loop:

```text
task workspace -> Hermes context -> final.py -> verify feedback loop -> packed recipe
```

```bash
scripts/afterai-relay task init "example title smoke"
scripts/afterai-relay task init "example title smoke" --template example-title
scripts/afterai-relay task run <run_id>
scripts/afterai-relay task context <run_id>
scripts/afterai-relay task context <run_id> --write
scripts/afterai-relay task loop <run_id> --agent-command "python3 /path/to/agent.py" --max-attempts 3
scripts/afterai-relay task loop <run_id> --agent-command scripts/afterai-relay-agent-example --max-attempts 1
scripts/afterai-relay task verify <run_id>
scripts/afterai-relay task pack <run_id> --name example-title
scripts/afterai-relay task list
scripts/afterai-relay task show <run_id>
scripts/afterai-relay task artifacts <run_id>
scripts/afterai-relay task network <run_id> add --json-file request.json
scripts/afterai-relay task network <run_id> search --url api --method GET
scripts/afterai-relay task network <run_id> export
scripts/afterai-relay task init-script <run_id> add webdriver --file init/webdriver.js
scripts/afterai-relay task init-script <run_id> list
scripts/afterai-relay cleanup
scripts/afterai-relay cleanup --execute
scripts/afterai-relay stealth doctor --preset cf-sensitive
scripts/afterai-relay artifacts <run_id>
scripts/afterai-relay relay /relay task init "example title smoke"

scripts/afterai-relay recipe list
scripts/afterai-relay recipe show example-title
scripts/afterai-relay recipe run example-title --param month=2026-05

scripts/afterai-relay --json doctor webwright
```

Default runtime paths:

```text
~/.local/share/afterai-relay/runs/<run_id>/
├── task.md
├── manifest.json
├── scripts/final.py
├── logs/
├── screenshots/
├── traces/
├── results/
├── agent/
└── verification/
```

`task run` executes `scripts/final.py` once, captures `logs/run.log`, injects `AFTERAI_RELAY_CDP_URL`, and marks the manifest `ran` or `failed`.

`task context` is the Hermes-native workflow primitive. It returns `afterai-relay-hermes-workflow-context-v1`: task, rail, editable files, verify/show/artifacts commands, current verification state, evidence summary, and metadata-only artifact paths. This is the preferred integration when Hermes itself is the agent: Hermes edits `scripts/final.py`, runs `task verify`, reads structured feedback/evidence, and never sends artifact contents to chat by default. `--write` stores the same context at `agent/hermes-context.json` for repeatable handoff.

`task loop` is the public-safe external-agent bridge. It writes `agent/request-NNN.json`, runs the external `--agent-command` with `AFTERAI_RELAY_AGENT_CONTEXT`, then calls `task verify`. If verification fails, the next request includes the redacted previous failure under `previous_result`. Loop artifacts stay inside `agent/`: request JSON, feedback JSON, redacted command logs, and `loop-result.json`.

`scripts/afterai-relay-agent-example` is a bundled deterministic external-agent example. It reads `AFTERAI_RELAY_AGENT_CONTEXT`, writes a public-safe `scripts/final.py`, and lets `task loop` complete without any LLM provider. Replace it with a private command such as a Hermes/OpenClaw wrapper when deploying real autonomous generation.

Agent command contract:

```text
input:  AFTERAI_RELAY_AGENT_CONTEXT=/path/to/agent/request-001.json
output: write or update runs/<id>/scripts/final.py plus any private-local artifacts
rule:   do not dump cookies, auth headers, browser profiles, or raw tokens
```

`task verify` is the completion gate. It compiles and runs `scripts/final.py`, captures a redacted `logs/verify.log`, requires fresh final logs/results or screenshots from the current verify attempt, writes `verification/verify-result.json`, runs a hygiene scan into `verification/hygiene-report.json`, and updates `manifest.json` to `verified` or `failed`. It currently implements `same-rail`; unimplemented strengths fail closed instead of pretending isolation.

Network observations are metadata-first: token-like query values, auth/cookie headers, and request/response bodies are redacted or omitted. `task network add/search/export` keeps this evidence private-local and never prints raw captured content by default. Init scripts are stored per task and reported only by name, byte size, and SHA-256; use them only for explicitly approved task runs, never to mutate a long-lived authenticated rail.

`doctor webwright` reports the exact CDP binding, browser/root/container hints, and redacted proxy diagnostics. `cleanup` is dry-run by default and blocks outside-base and symlink targets. Upload helpers require `AFTERAI_RELAY_UPLOAD_ALLOWED_DIRS` and reject relative, missing, directory, symlink, or outside-root paths. `stealth doctor` is diagnostic-only: it checks consistency and classifies samples, but makes no CAPTCHA or Cloudflare-bypass claim.

Hardening rules: run IDs cannot contain path components or escape `runs_dir`; browser cookie/profile dumps (`Cookies`, `Local State`, SQLite DBs, HARs, symlinks) fail hygiene; agent command failures return structured gates such as `agent_command_not_found` or `agent_command_timeout`.

`task show` is the production adapter report: compact operator evidence only (run, rail, local CDP label, verification, artifact count, hygiene, blocker). `artifacts <run_id>` and `task artifacts <run_id>` return metadata-only artifact indexes with paths, sizes, and sensitivity. They do not print file contents and authenticated artifacts stay `private-local/no-auto-send` unless a separate policy-cleared export is added.

`relay [/relay] ...` is the Telegram/operator adapter surface. It accepts slash-command-shaped tokens such as `relay /relay task init "check example"`, strips the optional `/relay` prefix, routes to task/recipe/artifact commands, and returns the same evidence-only JSON or compact text reports. Unknown commands fail closed with `unknown_relay_command`.

`--template example-title` generates a Playwright/CDP smoke script that connects to `http://127.0.0.1:18800`, opens `example.com`, writes `results/result.json`, and saves `screenshots/999-final.png`. The default template stays placeholder-safe for CI and offline development.

`task pack` only packs verified runs. It copies `final.py` and `recipe.json` into `~/.local/share/afterai-relay/recipes/<name>/`; it does not copy logs, screenshots, traces, results, or profile data.

## Backend switching

Switching is just relaunching with a different backend:

```bash
scripts/afterai-relay kill
scripts/afterai-relay launch --backend browseros
scripts/afterai-relay status

scripts/afterai-relay kill
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay status
```

`auto` tries CloakBrowser first, then BrowserOS, then system Chromium.

## CDP use

Connect Playwright:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    page = browser.contexts[0].new_page()
    page.goto("https://example.com")
    print(page.title())
    browser.close()
```

## Systemd watchdog example

```ini
# ~/.config/systemd/user/afterai-relay.service
[Unit]
Description=afterai-relay browser CDP

[Service]
Type=simple
WorkingDirectory=%h/afterai-relay
ExecStart=%h/afterai-relay/scripts/afterai-relay launch --backend auto --foreground
ExecStop=%h/afterai-relay/scripts/afterai-relay kill
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now afterai-relay.service
```

## Public hygiene checks

```bash
python3 tests/test_public_hygiene.py
python3 tests/test_shell_syntax.py
python3 /path/to/create-skill/scripts/skill_workflow_guard.py .
```
