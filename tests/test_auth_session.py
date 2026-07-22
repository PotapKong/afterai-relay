#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from afterai_relay.auth import (
    AuthConfig,
    _assert_loopback_listener,
    _wait_public_http,
    parse_cloudflared_url,
    public_status,
    stop_session,
    validate_loopback,
)


class AuthSessionTests(unittest.TestCase):
    def test_parse_cloudflared_url(self) -> None:
        text = "INF Your quick Tunnel has been created! Visit https://quiet-river.trycloudflare.com"
        self.assertEqual(parse_cloudflared_url(text), "https://quiet-river.trycloudflare.com")
        self.assertIsNone(parse_cloudflared_url("no tunnel yet"))

    def test_loopback_binding_is_mandatory(self) -> None:
        for host in ("127.0.0.1", "localhost", "::1"):
            validate_loopback(host)
        for host in ("all-interfaces", "example.com"):
            with self.assertRaises(ValueError):
                validate_loopback(host)

    def test_public_status_never_contains_password_material(self) -> None:
        state = {
            "state": "up",
            "publicUrl": "https://example.trycloudflare.com/vnc.html",
            "expiresAt": 123,
            "password": "forbidden",
            "passwordFile": "/tmp/secret",
            "pids": {"vnc": 1},
        }
        payload = public_status(state)
        serialized = json.dumps(payload)
        self.assertNotIn("forbidden", serialized)
        self.assertNotIn("password", serialized.lower())
        self.assertEqual(payload["state"], "up")

    def test_stop_removes_ephemeral_files_but_preserves_profile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            password_file = root / "vnc.pass"
            state_file = root / "state.json"
            profile = root / "profile"
            profile.mkdir()
            (profile / "keep.txt").write_text("keep")
            password_file.write_text("temporary")
            state_file.write_text(json.dumps({
                "state": "up",
                "passwordFile": str(password_file),
                "profileDir": str(profile),
                "pids": {},
            }))
            with mock.patch("afterai_relay.auth._terminate_pid"):
                result = stop_session(state_file)
            self.assertEqual(result["state"], "down")
            self.assertFalse(password_file.exists())
            self.assertFalse(state_file.exists())
            self.assertEqual((profile / "keep.txt").read_text(), "keep")

    def test_listener_check_requires_actual_loopback_bind(self) -> None:
        good = mock.Mock(returncode=0, stdout="LISTEN 0 32 127.0.0.1:5901 0.0.0.0:*\n", stderr="")
        with mock.patch("afterai_relay.auth._require_binary", return_value="/usr/bin/ss"), mock.patch("afterai_relay.auth.subprocess.run", return_value=good):
            _assert_loopback_listener(5901)
        wildcard = mock.Mock(returncode=0, stdout="LISTEN 0 32 0.0.0.0:5901 0.0.0.0:*\n", stderr="")
        with mock.patch("afterai_relay.auth._require_binary", return_value="/usr/bin/ss"), mock.patch("afterai_relay.auth.subprocess.run", return_value=wildcard), self.assertRaisesRegex(RuntimeError, "not loopback-only"):
            _assert_loopback_listener(5901)

    def test_quick_tunnel_url_must_answer_http_before_handoff(self) -> None:
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        opener = mock.MagicMock()
        opener.open.return_value = response
        with mock.patch("afterai_relay.auth.urllib.request.build_opener", return_value=opener):
            _wait_public_http("https://quiet-river.trycloudflare.com", timeout=1)
        opener.open.assert_called_once()

    def test_config_defaults_to_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = AuthConfig.from_env(base_dir=Path(td), display=":1002", profile_dir=Path(td) / "profile")
            self.assertEqual(cfg.vnc_host, "127.0.0.1")
            self.assertEqual(cfg.novnc_host, "127.0.0.1")
            self.assertGreaterEqual(cfg.ttl_seconds, 300)


if __name__ == "__main__":
    unittest.main()
