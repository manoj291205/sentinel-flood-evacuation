"""Lane S own tests for P34B: deploy_check failure paths (no network beyond localhost)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("deploy_check_own", ROOT / "scripts" / "deploy_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unreachable_server_fails_without_leaking_the_password(capsys, monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    code = _module().main(["http://127.0.0.1:9", "--password", "never-print-this", "--timeout", "1"])
    out = capsys.readouterr().out
    assert code != 0
    assert "FAIL health" in out and "never-print-this" not in out
