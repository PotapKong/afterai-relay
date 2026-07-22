# Authenticated browser sessions

Use a persistent Relay profile when an agent must work inside Google or another authenticated web service without handling the user's password, 2FA code, cookies, or API token in chat.

## Safe workflow

1. Launch the persistent browser rail with CloakBrowser and verify CDP health:

   ```bash
   scripts/afterai-relay launch --backend cloakbrowser
   scripts/afterai-relay health
   scripts/afterai-relay --json status
   ```

2. Open the service login page inside that profile:

   ```bash
   scripts/afterai-relay open https://accounts.google.com/
   ```

3. Automate only the non-secret navigation. Stop at password, passkey, security-key, CAPTCHA, consent, or 2FA UI.

4. Give the user a temporary interactive view of the same display/profile. On a headless host, the preferred pattern is:
   - VNC/noVNC bound to loopback only;
   - an authenticated or one-time HTTPS tunnel;
   - random short-lived access password;
   - strict timeout and explicit shutdown after login;
   - no screenshots, recordings, clipboard capture, cookie export, or auth-page artifacts.

5. The user enters credentials and completes 2FA personally. The agent must never ask the user to send passwords, passkeys, recovery codes, cookies, or long-lived API tokens through chat.

6. Verify login only through non-secret evidence: destination host, account-menu presence, or authenticated landing-page state. Never print cookie values, authorization headers, profile files, or token material.

7. Close the temporary interactive channel immediately. Keep only the persistent browser profile under the Relay runtime directory with restrictive filesystem permissions.

8. Reuse the authenticated profile for later browser work. If Google or the service requests re-verification, repeat the user-controlled interactive step rather than extracting credentials.

## Google-specific notes

- CloakBrowser can reach Google's password/passkey challenge where ordinary automation browsers may be rejected. Treat this as a compatibility path, not a promise that every risk challenge will pass.
- Native passkey dialogs may not appear in page DOM or Playwright screenshots. Do not infer success from a page saying “Verifying”; require the authenticated destination page.
- “Try another way” may expose password or passkey choices. Selecting a method is safe; completing it belongs to the user.
- Do not disable Google account security, weaken 2FA, or create app passwords merely to make automation easier.

## Implemented `auth` command

Relay implements:

```bash
scripts/afterai-relay auth start --tunnel cloudflared --ttl 900 https://accounts.google.com/
scripts/afterai-relay auth status
scripts/afterai-relay auth stop
```

Operational guarantees:

- default to `127.0.0.1` binds;
- generate credentials per run and never persist them in repo/state/logs;
- refuse public bind without an authenticated tunnel;
- auto-expire the session;
- `auth start` returns the one-time VNC access code exactly once; `auth status` returns metadata only and never repeats it;
- delete any captured `auth start` output immediately after delivering the short-lived code;
- `auth stop` must terminate tunnel/VNC processes while preserving the browser profile;
- add tests for loopback binding, expiry, redaction, cleanup, and failure-closed behavior.

### Bind verification and quick-tunnel readiness

Before exposing an interactive session, prove that **both** VNC and noVNC are loopback-only with `ss` or an equivalent listener check. Do not trust only the configured host value: on some `x11vnc` builds, `-listen 127.0.0.1` can still create a wildcard IPv6 listener. Use x11vnc's explicit `-localhost` mode and require listeners limited to `127.0.0.1` and/or `::1`; otherwise stop the session and fix the bind before issuing a URL.

Cloudflare may print a `trycloudflare.com` URL before its DNS record is visible through every resolver. Treat the URL as provisional until the tunnel log shows a registered connection **and** an independent external HTTP fetch reaches the noVNC page. Use one short bounded readiness check; never hand the user a URL that has not passed it. If readiness fails, stop all auth processes. A single fresh tunnel is a reasonable retry, but do not keep cycling random Quick Tunnel URLs in the same handoff. Offer a named Cloudflare Tunnel protected by Access (`references/named-cloudflare-access.md`) or a private overlay network instead.

Host dependencies: `x11vnc`, `novnc`, `websockify`, `tigervnc-tools`; `cloudflared` is required only for the temporary public tunnel.

## Verification checklist

- Relay health is `HEALTH_OK`.
- The persistent profile directory is outside the repository.
- The user—not the agent—completed password/passkey/2FA.
- No secret appeared in chat, command arguments, logs, screenshots, or artifacts.
- The authenticated service page was reached.
- Temporary interactive access was stopped and verified down.
