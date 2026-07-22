# Multi-rail isolation for authenticated browser work

Use this when more than one Relay browser may exist on the same host. A separate profile path alone is insufficient: Relay treats any already-listening CDP port as a healthy existing rail and does not prove that its browser owns the requested profile.

## Isolation contract

Give every sensitive workflow a unique tuple:

```bash
export AFTERAI_RELAY_BASE_DIR="$HOME/.local/share/afterai-relay-<scope>"
export AFTERAI_RELAY_PROFILE="<scope>"
export AFTERAI_RELAY_PROFILE_DIR="$AFTERAI_RELAY_BASE_DIR/profiles/$AFTERAI_RELAY_PROFILE"
export AFTERAI_RELAY_PORT=18801          # unique per rail
export AFTERAI_RELAY_DISPLAY=:1003        # unique headed X display
export AFTERAI_RELAY_HOST=127.0.0.1
```

Create the runtime and profile with owner-only permissions before launch:

```bash
umask 077
mkdir -p "$AFTERAI_RELAY_PROFILE_DIR"
chmod 700 "$AFTERAI_RELAY_BASE_DIR" \
  "$AFTERAI_RELAY_BASE_DIR/profiles" \
  "$AFTERAI_RELAY_PROFILE_DIR"
```

## Required verification before login

1. Launch the rail.
2. Check `afterai-relay health`.
3. Get `afterai-relay --json status`.
4. Require all three facts before creating temporary VNC/noVNC access:
   - CDP URL equals the expected `127.0.0.1:<unique-port>`;
   - CDP state is `up`;
   - `ownerCmdline` includes the exact expected `--user-data-dir`.

Do not rely on the reported `profileDir` field alone. It is configuration state and can name the requested profile even if a browser already listening on the reused port belongs to another profile.

## Privacy guard

Never call `tabs` / raw `/json/list` on a rail whose owner has not passed the verification above. CDP target listings can reveal titles and URLs of unrelated authenticated tabs. If verification fails, stop using that rail; do not inspect it. Start an isolated rail on a new base directory, port, and display instead.

## Login closeout

After the user confirms login, verify only non-secret authenticated state in the verified rail. Close the temporary VNC/noVNC tunnel immediately. Preserve the isolated browser profile; do not export cookies, headers, screenshots of auth screens, or target listings.