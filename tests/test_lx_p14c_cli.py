"""CLI safeguards for the code-only Phase 14C milestone."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from scripts import phase14c_run_claim_support as runner


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Phase 14C code tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.mark.parametrize("has_key", [False, True])
def test_check_env_reports_presence_only(monkeypatch, capsys, tmp_path, has_key):
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["phase14c_run_claim_support.py", "--check-env"])
    secret = "private-test-key-do-not-print"
    if has_key:
        monkeypatch.setenv("GROQ_API_KEY", secret)
    else:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert runner.main() == 0
    output = capsys.readouterr().out
    assert f"key {'present' if has_key else 'missing'}" in output
    assert secret not in output


def test_dry_run_uses_temporary_output_and_no_live_transport(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path / "real-results")
    monkeypatch.setattr(sys, "argv", ["phase14c_run_claim_support.py", "--dry-run", "--max-requests", "1"])
    observed = []

    def fake_run(*, transport, out_dir: Path, max_requests, zdr_attested):
        observed.append((transport, out_dir, max_requests, zdr_attested))
        assert out_dir != runner.DEFAULT_OUT_DIR
        assert transport is runner._fake_transport
        assert max_requests == 1 and zdr_attested
        return {"done": 1, "total": 135, "requests_made": 1,
                "tokens_counted": 100, "stopped_reason": "MAX_REQUESTS"}

    monkeypatch.setattr(runner, "run", fake_run)
    assert runner.main() == 0
    assert len(observed) == 1
    assert not runner.DEFAULT_OUT_DIR.exists()


def test_live_guards_stop_before_transport(monkeypatch):
    monkeypatch.setattr(runner, "_protocol_committed", lambda: True)
    monkeypatch.setattr(runner, "run", lambda **kwargs: pytest.fail("live transport was reached"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["phase14c_run_claim_support.py", "--live", "--attest-zdr"])
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        runner.main()

    monkeypatch.setenv("GROQ_API_KEY", "private-test-key-do-not-print")
    monkeypatch.setattr(sys, "argv", ["phase14c_run_claim_support.py", "--live"])
    with pytest.raises(RuntimeError, match="ZDR"):
        runner.main()

    monkeypatch.setattr(runner, "_protocol_committed", lambda: False)
    monkeypatch.setattr(sys, "argv", ["phase14c_run_claim_support.py", "--live", "--attest-zdr"])
    with pytest.raises(RuntimeError, match="protocol"):
        runner.main()
