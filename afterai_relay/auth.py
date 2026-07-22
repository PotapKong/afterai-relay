from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import socket
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
PROCESS_MARKERS = {
    "vnc": "x11vnc",
    "novnc": "websockify",
    "tunnel": "cloudflared",
    "expiry": "afterai_relay.auth",
}


@dataclass(frozen=True)
class AuthConfig:
    auth_dir: Path
    state_file: Path
    password_file: Path
    log_dir: Path
    profile_dir: Path
    display: str
    vnc_host: str
    vnc_port: int
    novnc_host: str
    novnc_port: int
    ttl_seconds: int

    @classmethod
    def from_env(cls, *, base_dir: Path, display: str, profile_dir: Path) -> "AuthConfig":
        auth_dir = Path(os.environ.get("AFTERAI_RELAY_AUTH_DIR", str(base_dir / "auth"))).expanduser().resolve()
        ttl = int(os.environ.get("AFTERAI_RELAY_AUTH_TTL", "900"))
        ttl = max(300, min(ttl, 3600))
        return cls(
            auth_dir=auth_dir,
            state_file=auth_dir / "state.json",
            password_file=auth_dir / "vnc.pass",
            log_dir=auth_dir / "logs",
            profile_dir=profile_dir.expanduser().resolve(),
            display=display,
            vnc_host=os.environ.get("AFTERAI_RELAY_AUTH_VNC_HOST", "127.0.0.1"),
            vnc_port=int(os.environ.get("AFTERAI_RELAY_AUTH_VNC_PORT", "5901")),
            novnc_host=os.environ.get("AFTERAI_RELAY_AUTH_NOVNC_HOST", "127.0.0.1"),
            novnc_port=int(os.environ.get("AFTERAI_RELAY_AUTH_NOVNC_PORT", "6080")),
            ttl_seconds=ttl,
        )


def validate_loopback(host: str) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"auth services must bind to loopback, got {host!r}")


def parse_cloudflared_url(text: str) -> str | None:
    match = TUNNEL_RE.search(text)
    return match.group(0) if match else None


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "down"}
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {"state": "invalid"}
    except Exception:
        return {"state": "invalid"}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError):
        return False


def _pid_cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
    except Exception:
        return ""


def _terminate_pid(pid: int, marker: str) -> None:
    if not pid or pid == os.getpid() or not _pid_alive(pid):
        return
    cmdline = _pid_cmdline(pid)
    if marker not in cmdline:
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.time() + 3
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.05)
    if _pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def public_status(state: dict[str, Any]) -> dict[str, Any]:
    raw_pids = state.get("pids")
    pids: dict[str, Any] = raw_pids if isinstance(raw_pids, dict) else {}
    return {
        "state": state.get("state", "down"),
        "publicUrl": state.get("publicUrl"),
        "localUrl": state.get("localUrl"),
        "startedAt": state.get("startedAt"),
        "expiresAt": state.get("expiresAt"),
        "tunnel": state.get("tunnel", "none"),
        "processes": {name: _pid_alive(int(pid)) for name, pid in pids.items() if name != "expiry" and str(pid).isdigit()},
    }


def stop_session(state_file: Path) -> dict[str, Any]:
    state = _read_state(state_file)
    raw_pids = state.get("pids")
    pids: dict[str, Any] = raw_pids if isinstance(raw_pids, dict) else {}
    for name in ("tunnel", "novnc", "vnc", "expiry"):
        try:
            pid = int(pids.get(name) or 0)
        except (TypeError, ValueError):
            pid = 0
        _terminate_pid(pid, PROCESS_MARKERS[name])
    password_path = Path(str(state.get("passwordFile") or state_file.parent / "vnc.pass"))
    try:
        password_path.unlink(missing_ok=True)
    except OSError:
        pass
    state_file.unlink(missing_ok=True)
    return {"state": "down", "stopped": True, "profilePreserved": True}


def _require_binary(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"missing dependency: {name}")
    return value


def _wait_port(host: str, port: int, timeout: float = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.15)
    raise RuntimeError(f"service did not open {host}:{port}")


def _spawn(command: list[str], log_path: Path) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = open(log_path, "ab", buffering=0)
    try:
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log.close()


def _make_vnc_password(password: str, path: Path) -> None:
    passwd_bin = _require_binary("tigervncpasswd")
    result = subprocess.run(
        [passwd_bin, "-f"],
        input=(password + "\n").encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("failed to create temporary VNC credential")
    path.write_bytes(result.stdout)
    path.chmod(0o600)


def _find_novnc_root() -> Path:
    candidates = [Path("/usr/share/novnc"), Path("/usr/share/novnc/utils/../")]
    for candidate in candidates:
        if (candidate / "vnc.html").exists():
            return candidate.resolve()
    raise RuntimeError("missing noVNC web root")


def _wait_tunnel_url(log_path: Path, timeout: float = 20) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = log_path.read_text("utf-8", errors="ignore") if log_path.exists() else ""
        url = parse_cloudflared_url(text)
        if url:
            return url
        time.sleep(0.25)
    raise RuntimeError("cloudflared did not return a quick-tunnel URL")


def start_session(config: AuthConfig, *, tunnel: str = "none") -> dict[str, Any]:
    validate_loopback(config.vnc_host)
    validate_loopback(config.novnc_host)
    if tunnel not in {"none", "cloudflared"}:
        raise ValueError("tunnel must be none or cloudflared")
    existing = _read_state(config.state_file)
    if existing.get("state") == "up" and any(public_status(existing).get("processes", {}).values()):
        raise RuntimeError("auth session already running")
    stop_session(config.state_file)

    for directory in (config.auth_dir, config.log_dir, config.profile_dir):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)

    x11vnc = _require_binary("x11vnc")
    websockify = _require_binary("websockify")
    if tunnel == "cloudflared":
        _require_binary("cloudflared")
    novnc_root = _find_novnc_root()
    password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    _make_vnc_password(password, config.password_file)

    processes: dict[str, subprocess.Popen[bytes]] = {}
    try:
        processes["vnc"] = _spawn([
            x11vnc,
            "-display", config.display,
            "-rfbauth", str(config.password_file),
            "-rfbport", str(config.vnc_port),
            # x11vnc's -listen 127.0.0.1 can still create a wildcard IPv6
            # listener on some builds. -localhost is its explicit loopback-only
            # mode and keeps the temporary VNC service off public interfaces.
            "-localhost",
            "-forever", "-shared", "-noxdamage", "-quiet",
        ], config.log_dir / "x11vnc.log")
        _wait_port(config.vnc_host, config.vnc_port)

        processes["novnc"] = _spawn([
            websockify,
            "--web", str(novnc_root),
            f"{config.novnc_host}:{config.novnc_port}",
            f"{config.vnc_host}:{config.vnc_port}",
        ], config.log_dir / "websockify.log")
        _wait_port(config.novnc_host, config.novnc_port)

        public_url = None
        if tunnel == "cloudflared":
            tunnel_log = config.log_dir / "cloudflared.log"
            tunnel_log.write_text("", encoding="utf-8")
            processes["tunnel"] = _spawn([
                "cloudflared", "tunnel", "--no-autoupdate", "--url",
                f"http://{config.novnc_host}:{config.novnc_port}",
            ], tunnel_log)
            public_url = _wait_tunnel_url(tunnel_log)

        now = int(time.time())
        state = {
            "state": "up",
            "startedAt": now,
            "expiresAt": now + config.ttl_seconds,
            "localUrl": f"http://{config.novnc_host}:{config.novnc_port}/vnc.html?autoconnect=true&resize=scale",
            "publicUrl": f"{public_url}/vnc.html?autoconnect=true&resize=scale" if public_url else None,
            "tunnel": tunnel,
            "display": config.display,
            "profileDir": str(config.profile_dir),
            "passwordFile": str(config.password_file),
            "pids": {name: proc.pid for name, proc in processes.items()},
        }
        _write_state(config.state_file, state)
        expiry = subprocess.Popen(
            [sys.executable, "-m", "afterai_relay.auth", "expire", "--state-file", str(config.state_file), "--ttl", str(config.ttl_seconds)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        state["pids"]["expiry"] = expiry.pid
        _write_state(config.state_file, state)
        result = public_status(state)
        result["oneTimeAccessCode"] = password
        result["expiresInSeconds"] = config.ttl_seconds
        return result
    except Exception:
        for name, proc in reversed(list(processes.items())):
            _terminate_pid(proc.pid, PROCESS_MARKERS[name])
        config.password_file.unlink(missing_ok=True)
        config.state_file.unlink(missing_ok=True)
        raise


def session_status(state_file: Path) -> dict[str, Any]:
    state = _read_state(state_file)
    expires_at = int(state.get("expiresAt") or 0)
    if state.get("state") == "up" and expires_at and time.time() >= expires_at:
        stop_session(state_file)
        return {"state": "down", "expired": True}
    return public_status(state)


def _config_from_args(args: argparse.Namespace) -> AuthConfig:
    if args.ttl is not None:
        os.environ["AFTERAI_RELAY_AUTH_TTL"] = str(args.ttl)
    return AuthConfig.from_env(
        base_dir=Path(args.base_dir).expanduser().resolve(),
        display=args.display,
        profile_dir=Path(args.profile_dir).expanduser().resolve(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="afterai-relay auth")
    parser.add_argument("action", choices=["start", "status", "stop", "expire"])
    parser.add_argument("--base-dir", default=os.environ.get("AFTERAI_RELAY_BASE_DIR", "~/.local/share/afterai-relay"))
    parser.add_argument("--profile-dir", default=os.environ.get("AFTERAI_RELAY_PROFILE_DIR", "~/.local/share/afterai-relay/profiles/default"))
    parser.add_argument("--display", default=os.environ.get("AFTERAI_RELAY_DISPLAY", os.environ.get("DISPLAY", ":1002")))
    parser.add_argument("--tunnel", choices=["none", "cloudflared"], default="none")
    parser.add_argument("--state-file")
    parser.add_argument("--ttl", type=int)
    args = parser.parse_args(argv)

    if args.action == "expire":
        if not args.state_file:
            parser.error("expire requires --state-file")
        time.sleep(max(1, args.ttl or 900))
        state_file = Path(args.state_file)
        state = _read_state(state_file)
        if isinstance(state.get("pids"), dict):
            state["pids"].pop("expiry", None)
            _write_state(state_file, state)
        stop_session(state_file)
        return 0

    config = _config_from_args(args)
    try:
        if args.action == "start":
            payload = start_session(config, tunnel=args.tunnel)
        elif args.action == "status":
            payload = session_status(config.state_file)
        else:
            payload = stop_session(config.state_file)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
