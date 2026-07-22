---
name: afterai-relay
description: Portable browser relay skill for Hermes/agent automation. Use when you need a local CDP browser rail with switchable CloakBrowser and BrowserOS backends, persistent profiles, health checks, tab/open commands, or a public-safe /relay-style setup without private host paths or secrets.
version: 0.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [browser, cdp, automation, cloakbrowser, browseros, relay]
---

# afterai-relay

Portable `/relay`-style browser rail for agents.

Use this skill when the user asks to:
- install or operate a local browser automation relay;
- switch between CloakBrowser and BrowserOS;
- expose a safe local Chrome DevTools Protocol endpoint for Playwright/Puppeteer/CDP tools;
- keep a persistent browser profile for authenticated automation;
- diagnose bot-detection/browser fingerprint issues without copying private cookies or secrets.

## Core model

`afterai-relay` is a small CDP supervisor around two browser paths:

1. **CloakBrowser** — patched Chromium, stealth/fingerprint-oriented automation path.
2. **BrowserOS** — Chromium-compatible browser with optional MCP/agent capabilities.

Backend selection is explicit and reversible:

```bash
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay launch --backend browseros
scripts/afterai-relay launch --backend auto
scripts/afterai-relay status
scripts/afterai-relay health
scripts/afterai-relay open https://example.com
scripts/afterai-relay kill
```

## Public-safe defaults

No secrets, cookies, private hostnames, IP allowlists, or user-specific paths are stored in this repo.

Runtime state defaults to the current user's home directory:

```text
~/.local/share/afterai-relay/
├── profiles/default/
├── logs/
└── state.json
```

Override with environment variables or a local env file copied from `templates/afterai-relay.env.example`.

## Quick install

```bash
git clone https://github.com/<owner>/afterai-relay.git
cd afterai-relay
scripts/install-cloakbrowser.sh
scripts/afterai-relay doctor
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay health
```

BrowserOS is optional. Install it separately, then run:

```bash
scripts/afterai-relay launch --backend browseros
```

## Recommended first-time setup sequence

```bash
scripts/afterai-relay doctor
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay health
```

This sequence was verified to produce `HEALTH_OK` when CloakBrowser is already present.

## Operator checklist

1. Run `scripts/afterai-relay doctor`.
2. Pick backend: `cloakbrowser`, `browseros`, or `auto`.
3. Launch and verify `http://127.0.0.1:${AFTERAI_RELAY_PORT:-18800}/json/version`.
4. Use CDP clients only on loopback or through a trusted tunnel.
5. Never commit runtime profiles, cookies, logs, `.env`, or downloaded binaries.
6. For Webwright-style work, use the task layer and report evidence paths instead of pasting artifact contents.

## Authenticated session workflow

For Google or other authenticated services, keep credentials out of chat and preserve authentication only in the persistent browser profile. Automate navigation up to the password/passkey/2FA boundary, then let the user complete that step through a temporary protected interactive view of the same Relay display. Shut down the interactive channel immediately after verifying the authenticated landing page; never export cookies or auth headers.

This applies equally to user-authorized paid courses and private learning portals. The ordinary Hermes browser and the persistent Relay profile use separate browser stores, so access in one does not prove access in the other. When the user offers to authorize through Relay, open the exact requested page in the Relay profile, hand off only the short-lived interactive view, and use the preserved session only for the user-approved work.

Credential/auth discovery order:

1. Check whether the required secret is already configured without printing it.
2. Check whether the persistent Relay profile is already authenticated.
3. Try the target login through Relay/CloakBrowser before concluding Google blocks automation.
4. If password/passkey/2FA is required, use `auth start` so the user enters it directly in the browser.
5. Ask for an API token in chat only as a last resort; never ask for a Google password, recovery code, cookie, or 2FA code.
6. On an authenticated dashboard that displays credentials, never retrieve `document.body.innerText`, screenshots, form values, or arbitrary DOM text. Verify state only through non-secret structural evidence such as URL, title, presence of a known link, or a boolean selector. If a value must move into a local secret store, extract and write it in one local process that emits only success metadata and permissions.
7. Relay access expires by design and the access code is returned only once. If it expires or the user needs a fresh view, create a new short-lived session; never repeat an old code.

This order matters: Relay is the preferred path for preserving browser authorization and avoids unnecessary credential exchange in chat.

Read `references/authenticated-sessions.md` before operating this flow. The implemented commands are:

```bash
scripts/afterai-relay auth start --tunnel cloudflared --ttl 900 https://accounts.google.com/
scripts/afterai-relay auth status
scripts/afterai-relay auth stop
```

`auth start` returns a short-lived noVNC URL and a one-time VNC access code. VNC and noVNC bind to loopback; the public path is a temporary Cloudflare quick tunnel. The session expires automatically, and `auth stop` removes the VNC credential while preserving the browser profile.

### Time-sensitive handoff UX

- When the user asks for the Relay link again, run `auth status` first. Do not resend a stale URL or earlier one-time code.
- If the session is down, run `auth stop` (safe after expiry), then create a fresh `auth start` session aimed at the exact next page and give its URL and code once.
- For multi-stage authorization, create the new handoff already pointed at the next local or remote page. A successful login to a web dashboard does not prove a separate local integration is authorized; verify the real integration through a non-secret status endpoint before closing Relay.

## Authenticated CMS and course-editor work

When an authenticated target is a Tiptap-based course or CMS editor, use its own JSON/state API through Relay CDP rather than mutating rendered HTML. Preserve the pre-edit JSON, reuse custom-node attributes, wait for autosave, and verify with a reload. Detailed recipe: `references/tiptap-cdp-content-editing.md`.

## Webwright task commands

```bash
scripts/afterai-relay task init "example title smoke"
scripts/afterai-relay task run <run_id>
scripts/afterai-relay task context <run_id>
scripts/afterai-relay task context <run_id> --write
scripts/afterai-relay task loop <run_id> --agent-command "python3 /path/to/agent.py" --max-attempts 3
scripts/afterai-relay task loop <run_id> --agent-command scripts/afterai-relay-agent-example --max-attempts 1
scripts/afterai-relay task verify <run_id>
scripts/afterai-relay task show <run_id>
scripts/afterai-relay task artifacts <run_id>
scripts/afterai-relay task network <run_id> add --json-file request.json
scripts/afterai-relay task network <run_id> search --url api --method GET
scripts/afterai-relay task network <run_id> export
scripts/afterai-relay task init-script <run_id> add webdriver --file init/webdriver.js
scripts/afterai-relay task init-script <run_id> list
scripts/afterai-relay task upload <run_id> validate --file /absolute/path/to/file
scripts/afterai-relay cleanup
scripts/afterai-relay cleanup --execute
scripts/afterai-relay stealth doctor --preset cf-sensitive
scripts/afterai-relay artifacts <run_id>
scripts/afterai-relay relay /relay task init "example title smoke"
scripts/afterai-relay task pack <run_id> --name example-title
```

Production adapter rules:

- `task show` prints compact operator evidence: run, rail, local CDP label, verification, artifact count, hygiene, blocker.
- `relay [/relay] ...` maps Telegram/operator slash-command-shaped input to the safe task/recipe/artifact command surface and fails closed on unknown commands.
- `artifacts` returns metadata only: paths, types, sizes, sensitivity. It must not print log/screenshot/result contents.
- `task network` stores redacted request metadata under `network/`; sensitive headers/query tokens and bodies are not printed by default.
- `task init-script` stores pre-document JavaScript under `init_scripts/` and reports only name/size/SHA-256. Use it only for explicitly approved task runs; do not mutate persistent authenticated rails.
- `doctor webwright` includes browser environment, exact CDP binding, and redacted `AFTERAI_RELAY_PROXY` diagnostics. Credentialed proxy URLs fail closed because the Chromium launcher has no secure proxy-auth implementation.
- `cleanup` is dry-run by default and may only remove relay-managed paths inside `AFTERAI_RELAY_BASE_DIR`.
- `task upload <run> validate --file …` exposes the allowlist without performing an upload. It requires `AFTERAI_RELAY_UPLOAD_ALLOWED_DIRS` and rejects relative/outside/symlink paths.
- `stealth doctor` is diagnostic-only: presets report fingerprint/challenge state, not guaranteed Cloudflare bypass.
- Authenticated artifacts stay `private-local/no-auto-send` unless a separate policy-cleared export is built.
- `task context` is the Hermes-native workflow primitive: Hermes is the agent, `/relay` is the browser tool/substrate. It returns the editable `scripts/final.py`, verify/show/artifact commands, current verification state, evidence summary, and metadata-only artifact paths.
- Use `task context --write` to persist `agent/hermes-context.json` for repeatable handoff without exposing artifact contents in chat.
- Agent integrations that are not Hermes-in-process stay outside the public repo and connect through `--agent-command` plus `AFTERAI_RELAY_AGENT_CONTEXT`.
- `scripts/afterai-relay-agent-example` is a deterministic public-safe external-agent example for loop smoke tests; it is not a provider integration.
- Run IDs must not contain path components or escape `runs_dir`; verification must require fresh artifacts from the current attempt; browser cookie/profile dumps must fail hygiene.

## Output Contract

When using this skill, return compact operator evidence:

1. selected backend (`cloakbrowser`, `browseros`, `chromium`, or `auto` result);
2. CDP endpoint (`host:port`) and profile directory;
3. commands run;
4. verification result (`status`, `health`, or `/json/version` evidence);
5. any residual risk, especially CDP exposure or missing browser binary.

Never print cookie values, auth headers, browser profile contents, or local `.env` values.

## Quick Test Checklist

```bash
scripts/afterai-relay doctor
scripts/afterai-relay --json status
bash -n scripts/afterai-relay scripts/afterai-relay.sh scripts/install-cloakbrowser.sh scripts/afterai-relay-watchdog.sh
python3 -m py_compile afterai_relay/*.py
python3 tests/test_task_workspace.py
python3 tests/test_auth_session.py
python3 tests/test_task_verify.py
python3 tests/test_task_run_pack.py
python3 tests/test_recipe_commands.py
python3 tests/test_agent_loop.py
python3 tests/test_hermes_workflow_context.py -v
python3 tests/test_bundled_agent_example.py
python3 tests/test_production_adapter.py
python3 tests/test_relay_adapter.py -v
python3 tests/test_review_hardening.py -v
python3 tests/test_stealth_browser_mcp_adoption.py -v
python3 tests/test_public_hygiene.py
python3 tests/test_shell_syntax.py
```

Optional live backend checks:

```bash
scripts/install-cloakbrowser.sh
scripts/afterai-relay launch --backend cloakbrowser
scripts/afterai-relay health
scripts/afterai-relay kill
```

## Done Criteria

- Backend selection is explicit and reversible.
- CDP binds to loopback by default.
- Runtime state stays outside the repo.
- No secrets, cookies, private IPs, or user-specific absolute paths are committed.
- Shell syntax and public hygiene checks pass.
- `SKILL.md` loads as a Hermes skill and points to the operational docs.

## References

- `README.md` — full setup and command reference.
- `references/security.md` — public repo hygiene and CDP exposure rules.
- `references/authenticated-sessions.md` — safe persistent-profile login, loopback verification, temporary interactive access, and Quick Tunnel readiness.
- `references/multi-rail-isolation.md` — required unique runtime/port/display tuple and profile-ownership verification when more than one Relay rail exists.
- `references/named-cloudflare-access.md` — stable remote handoff with a user-owned Cloudflare domain and Access protection when Quick Tunnel is unsuitable.
- `templates/afterai-relay.env.example` — configuration template.
