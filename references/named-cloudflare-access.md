# Stable remote interactive access: Named Cloudflare Tunnel + Access

Use this when a temporary `trycloudflare.com` Quick Tunnel fails readiness checks, or when repeated authenticated-browser access needs a stable, protected hostname.

## Security model

```text
user's dedicated subdomain
→ Cloudflare Access (allow only the user's identity)
→ Named Cloudflare Tunnel (outbound from server)
→ noVNC on 127.0.0.1 only
→ isolated Relay browser rail
```

The server opens no inbound firewall ports. Keep CDP, VNC, and noVNC loopback-only; Cloudflare Tunnel is the only public ingress. Do not use an unprotected public hostname for an authenticated browser session.

## Prerequisites

- The user has a Cloudflare account with a domain/zone they control.
- The user completes Cloudflare login or OAuth themselves; never request dashboard passwords, API tokens, certificates, or cookies in chat.
- Use a dedicated hostname such as `relay-login.<domain>`, not a production app hostname.
- Set a Cloudflare Access policy before giving the URL to the user. Prefer one explicitly allowed email address and one-time PIN or the user's existing identity provider.

## Operational sequence

1. Confirm the isolated rail first: distinct runtime base, profile, CDP port, and X display. See `references/multi-rail-isolation.md`.
2. Create or connect a named tunnel through the user's Cloudflare account; keep tunnel credentials in local owner-only secret storage and never print them.
3. Route the dedicated hostname to `http://127.0.0.1:<noVNC-port>`.
4. Create a Cloudflare Access self-hosted application and an allow policy limited to the user.
5. Verify externally that the Access login appears, but do not bypass it or expose the raw noVNC origin.
6. Give the user the hostname. They complete Access and then the short-lived VNC password handoff themselves.
7. After login, shut down VNC/noVNC. Keep the named tunnel only if future interactive handoffs are expected; otherwise disable its public hostname or tunnel.

## When not to use Quick Tunnel

Quick Tunnels are suitable only for ad hoc development handoffs. Treat a generated URL as provisional. If it does not resolve and return HTTP 200 within a short bounded readiness window, stop the session rather than repeatedly sending fresh random URLs. Offer this named-tunnel pattern or a private overlay network instead.
