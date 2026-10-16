"""Lane X checks for Phase 14D CLI guards without network access."""

from __future__ import annotations

import importlib.util
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runner(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access in a Phase 14D test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    spec = importlib.util.spec_from_file_location("lx_phase14d_runner", ROOT / "scripts/phase14d_run_claim_support.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def invoke(monkeypatch, runner, *args):
    monkeypatch.setattr(sys, "argv", ["phase14d_run_claim_support.py", *args])
    return runner.main()


def test_check_env_never_prints_secret(monkeypatch, runner, capsys):
    secret = "private-key-test-value"
    monkeypatch.setenv("GROQ_API_KEY", secret)
    assert invoke(monkeypatch, runner, "--check-env") == 0
    output = capsys.readouterr().out
    assert "key present" in output and secret not in output
    monkeypatch.delenv("GROQ_API_KEY")
    assert invoke(monkeypatch, runner, "--check-env") == 0
    assert "key missing" in capsys.readouterr().out


def test_dry_run_leaves_results_untouched(monkeypatch, runner, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path / "results")
    original_tempdir = runner.tempfile.TemporaryDirectory
    monkeypatch.setattr(runner.tempfile, "TemporaryDirectory",
                        lambda **kwargs: original_tempdir(dir=tmp_path, **kwargs))
    assert invoke(monkeypatch, runner, "--dry-run", "--max-requests", "1") == 0
    assert not (tmp_path / "results").exists()


def test_live_guards_before_network(monkeypatch, runner, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path / "results")
    monkeypatch.setattr(runner, "FREEZE", tmp_path / "no_freeze.json")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        invoke(monkeypatch, runner, "--live", "--attest-zdr", "--set", "practice", "--round", "1",
               "--prompt", "14d-prompt-r0")
    monkeypatch.setenv("GROQ_API_KEY", "private-key-test-value")
    with pytest.raises(RuntimeError, match="ZDR"):
        invoke(monkeypatch, runner, "--live", "--set", "practice", "--round", "1",
               "--prompt", "14d-prompt-r0")
    with pytest.raises(ValueError, match="round 1"):
        invoke(monkeypatch, runner, "--live", "--attest-zdr", "--set", "practice", "--round", "2",
               "--prompt", "14d-prompt-r1")
    with pytest.raises(ValueError, match="frozen prompt"):
        invoke(monkeypatch, runner, "--live", "--attest-zdr", "--set", "test")
    assert not (tmp_path / "results").exists()


def test_modified_inputs_are_rejected(monkeypatch, runner, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "private-key-test-value")
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path / "results")
    seen = []

    def modified(paths):
        seen.extend(paths)
        return False

    monkeypatch.setattr(runner, "_tracked_and_clean", modified)
    with pytest.raises(RuntimeError, match="committed"):
        invoke(monkeypatch, runner, "--live", "--attest-zdr", "--set", "practice", "--round", "1",
               "--prompt", "14d-prompt-r0")
    assert runner.PROTOCOL in seen and runner.MANIFEST in seen
    assert runner.CHALLENGE_DIR / "challenge_practice.json" in seen
    assert runner.PROMPT_DIR / "14d-prompt-r0.txt" in seen
    assert not (tmp_path / "results").exists()
