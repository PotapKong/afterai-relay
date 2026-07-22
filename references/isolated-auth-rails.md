# Isolated authenticated browser rails

Use this when an agent needs a new browser login without touching an existing Relay profile.

## Isolation contract

Give every sensitive rail its own values; never reuse the default port, display, base directory, or state file:

```bash
AFTERAI_RELAY_BASE_DIR="$HOME/.local/share/afterai-relay-<service>"
AFTERAI_RELAY_PROFILE="<service>-content"
AFTERAI_RELAY_PROFILE_DIR="$AFTERAI_RELAY_BASE_DIR/profiles/$AFTERAI_RELAY_PROFILE"
AFTERAI_RELAY_HOST=127.0.0.1
AFTERAI_RELAY_PORT=<unused-port>
AFTERAI_RELAY_DISPLAY=:<unused-display>
```

Before asking the user to log in, verify that CDP is bound to the unique loopback port and that the browser owner command contains the expected `--user-data-dir`. Do **not** inspect `/json/list` on a rail whose identity was not proven: tab listings can expose unrelated private browsing context.

## Temporary user view

- Bind noVNC and VNC to loopback only. For x11vnc use `-localhost`; some builds can expose a wildcard IPv6 listener when invoked with `-listen 127.0.0.1`.
- Confirm listeners with `ss` before giving a URL; valid bindings are `127.0.0.1` and/or `::1`, never `0.0.0.0` or `[::]`.
- User enters password, passkey, CAPTCHA, and 2FA. Never request, print, export, or store them.
- Close the temporary tunnel immediately after login and verify that its listeners are gone.

## Quick Tunnel readiness

`trycloudflare.com` can print a hostname before it resolves publicly. Treat it as provisional. Check external DNS/HTTP readiness before sending the link. Use a bounded retry; if the hostname still does not resolve, stop the temporary session rather than giving the user a dead URL.

Quick Tunnels are suitable only for short-lived testing. For repeatable user access, prefer a named Cloudflare Tunnel protected by Cloudflare Access, or a tailnet-only route.
