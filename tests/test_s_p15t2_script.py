"""Lane S unit tests for scripts/phase15t2_tier_rules.py guards (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("phase15t2_tier_rules", ROOT / "scripts" / "phase15t2_tier_rules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_requires_zdr_attestation(monkeypatch):
    script = _script()
    monkeypatch.setattr(script, "load_tiered_rules", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert script.main(["--live"]) == 2


def test_live_refuses_to_overwrite_and_needs_key(tmp_path, monkeypatch):
    script = _script()
    monkeypatch.setattr(script, "load_tiered_rules", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    existing = tmp_path / "tier_results.json"
    existing.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    assert script.main(["--live", "--attest-zdr", "--out", str(existing)]) == 2
    monkeypatch.delenv("GROQ_API_KEY")
    assert script.main(["--live", "--attest-zdr", "--out", str(tmp_path / "new.json")]) == 2
    assert not (tmp_path / "new.json").exists()


def test_preflight_without_key_makes_no_call(monkeypatch):
    import httpx

    script = _script()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert script.preflight() == 2
