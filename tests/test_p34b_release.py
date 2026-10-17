"""Phase 34B acceptance tests (Lead) — release: POLICY count, deploy check, Docker, CI, dev scripts, docs.
Do not edit; escalate instead. Spec: specs/V4_RELEASE_SPEC.md. No network beyond a local stub server; no Docker run.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P34B")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"
DISCLOSURE = ("Until P0 is filed the deployment must be private or password-protected (SENTINEL_DEMO_PASSWORD); a public "
              "link is switched on only after the user confirms P0 is filed.")
LEGACY_NOTE = "Legacy V3 dashboard — the V4 web console (web/) replaces it."
PAGES = ("Overview", "Live Operations", "Decisions & Certificates", "Evidence & Results", "System & Hardware")


def _contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _text(relative):
    path = ROOT / relative
    assert path.is_file(), f"{relative} is missing"
    return path.read_text(encoding="utf-8")


# ---- POLICY in certificates (Wave B audit follow-up) -----------------------------------------------------------

RULE_TEXT = "Evacuees should not be moved over routes that take longer than forty minutes during flooding."


class _Futures:
    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


class _Future:
    start_timestep = 0
    steps = 50


def _rollout(c, k, ledger, world, params, graph, extra_terms=()):
    from src.certify.rollout import Outcome, RolloutResult

    elapsed = 50.0  # longer than the 40-minute rule: every future is rule-blocked when rules are active
    if extra_terms and not all(t(c, _Future(), 3, elapsed, (), ledger) for t in extra_terms):
        return RolloutResult(False, Outcome.POLICY, 3, -float(c.people), True, True, True, False)
    return RolloutResult(True, Outcome.OK, 3, float(c.people), True, True, True, True if extra_terms else None)


def _certificate(with_rules):
    from src.actuation.commands import InMemorySink
    from src.certify.certificate import validate_certificate
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params
    from src.constraints.claim_support import EvidenceChunk
    from src.constraints.ndma_rules import NdmaRule
    from src.constraints.tiering import Tier, assign_tier
    from src.geospatial import load_road_graph
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.safety import evaluate_actions

    digest = hashlib.sha256(RULE_TEXT.encode()).hexdigest()
    rule = NdmaRule("NDMA-T01", "at most forty minutes", "MAX_TRAVEL_MINUTES", {"minutes": 40}, {"minutes": 5},
                    {"source_id": "s", "filename": "f.pdf", "page": 1, "chunk_id": "c", "passage_sha256": digest,
                     "span": "longer than forty minutes"}, approved=True)
    rules = []
    if with_rules:
        tiered = assign_tier(rule, lambda r: EvidenceChunk("c", "s", "f.pdf", 1, RULE_TEXT, digest))
        assert tiered.tier is Tier.T1
        rules = [tiered]
    scenario, sim, graph, overlay, world = build_v4_runtime(
        "v4-medium-dt2-v1", generator_seed=620000, graph=load_road_graph())
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), SimLedgerAdapter(sim),
                         sink=InMemorySink(), futures_factory=_Futures, rollout=_rollout,
                         world_id="v4-medium-dt2-v1", rules=rules)
    sim.observe()
    state = sim.prepared_state_for_debug()
    result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
    cert = gate.commit(result, inputs, operator={"decision": "ACCEPT", "actor": "t", "reason": ""}).certificate
    validate_certificate(cert)
    return cert


def test_policy_count_is_written_when_rules_are_active():
    cert = _certificate(with_rules=True)
    assert "+rules-" in cert["params"]["params_id"]
    rows = [c for c in cert["candidates"] if c["action_key"] != "WAIT"]
    assert rows
    for row in rows:
        assert "POLICY" in row["outcome_counts"]
        assert sum(row["outcome_counts"].values()) == row["n"]
        assert row["outcome_counts"]["POLICY"] == row["n"]


def test_policy_count_is_absent_without_rules_and_fixture_hashes_hold():
    from src.certify.certificate import certificate_hash

    cert = _certificate(with_rules=False)
    assert all("POLICY" not in c["outcome_counts"] for c in cert["candidates"])
    for fixture in _contract("certificates_fixture.json")["certificates"]:
        assert certificate_hash(fixture) == fixture["cert_hash"]


# ---- deploy_check against a stub server -----------------------------------------------------------------------

def _load_deploy_check():
    path = ROOT / "scripts" / "deploy_check.py"
    assert path.is_file(), "scripts/deploy_check.py is missing"
    spec = importlib.util.spec_from_file_location("deploy_check_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub(password=None, tamper_detected=True):
    steps = _contract("demo_steps.json")["steps"]
    certs = _contract("certificates_fixture.json")["certificates"]
    evidence = {"simulated": True, "honesty": "stub", "source": "ARTIFACT", "items": [
        {"id": i["id"], "group": i["group"], "label": i["label"], "value": None, "display": "-", "unit": i["unit"],
         "source_path": i["path"], "source_sha256": None, "note": "stub"}
        for i in _contract("evidence_manifest.json")["items"]]}
    state = {"index": 0}
    expected = "Basic " + base64.b64encode(f"sentinel:{password}".encode()).decode() if password else None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, content_type="application/json", headers=()):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            for key, value in headers:
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _guarded(self):
            if expected and self.path != "/api/health" and self.headers.get("Authorization") != expected:
                self._send(401, {"detail": "auth"}, headers=[("WWW-Authenticate", 'Basic realm="sentinel"')])
                return True
            return False

        def _demo(self):
            return {"source": "FIXTURE", "step_index": state["index"], "step_count": len(steps),
                    "step": steps[state["index"]], "simulated": True, "honesty": "stub"}

        def do_GET(self):
            if self.path == "/api/health":
                return self._send(200, {"status": "ok", "version": "stub", "graph_fingerprint": "0" * 64,
                                        "simulated": True, "honesty": "stub", "source": "LIVE"})
            if self._guarded():
                return
            if self.path == "/":
                return self._send(200, '<!doctype html><div id="root"></div>', "text/html; charset=utf-8")
            if self.path == "/api/certificates":
                return self._send(200, {"certificates": certs, "simulated": True, "honesty": "stub", "source": "FIXTURE"})
            if self.path.startswith("/api/certificates/"):
                cid = self.path.rsplit("/", 1)[1]
                match = [c for c in certs if c["cert_id"] == cid]
                return self._send(200, match[0]) if match else self._send(404, {"detail": "nf"})
            if self.path == "/api/evidence":
                return self._send(200, evidence)
            return self._send(404, {"detail": "nf"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self._guarded():
                return
            if self.path == "/api/demo/start":
                state["index"] = 0
                return self._send(200, self._demo())
            if self.path == "/api/demo/step":
                state["index"] = min(state["index"] + 1, len(steps) - 1)
                return self._send(200, self._demo())
            if self.path.endswith("/replay"):
                bad = bool(body.get("tamper")) and tamper_detected
                return self._send(200, {"result": "MISMATCH" if bad else "MATCH",
                                        "mismatched_fields": ["forecast_hash"] if bad else []})
            return self._send(404, {"detail": "nf"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture()
def stub_factory():
    servers = []

    def make(**kwargs):
        server, url = _stub(**kwargs)
        servers.append(server)
        return url

    yield make
    for server in servers:
        server.shutdown()


def test_deploy_check_passes_a_conforming_protected_server(stub_factory, capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    check = _load_deploy_check()
    url = stub_factory(password="stub-only-password")
    report = tmp_path / "report.json"
    assert check.main([url, "--password", "stub-only-password", "--json", str(report)]) == 0
    out = capsys.readouterr().out
    for cid in [c["id"] for c in _contract("deploy_check.json")["checks"]]:
        assert f"PASS {cid}" in out
    assert "stub-only-password" not in out
    assert "stub-only-password" not in report.read_text(encoding="utf-8")


def test_deploy_check_reads_the_password_from_the_environment(stub_factory, capsys, monkeypatch):
    check = _load_deploy_check()
    url = stub_factory(password="env-only-password")
    monkeypatch.setenv("SENTINEL_DEMO_PASSWORD", "env-only-password")
    assert check.main([url]) == 0
    assert "env-only-password" not in capsys.readouterr().out


def test_deploy_check_open_server_without_password_skips_auth(stub_factory, capsys, monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    check = _load_deploy_check()
    assert check.main([stub_factory()]) == 0
    assert "FAIL" not in capsys.readouterr().out


def test_deploy_check_fails_when_tamper_is_not_detected(stub_factory, capsys, monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    check = _load_deploy_check()
    assert check.main([stub_factory(tamper_detected=False)]) != 0
    assert "FAIL replay-tamper" in capsys.readouterr().out


def test_deploy_check_fails_when_a_password_is_expected_but_the_server_is_open(stub_factory, capsys, monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    check = _load_deploy_check()
    assert check.main([stub_factory(), "--password", "expected-password"]) != 0
    assert "FAIL auth-required" in capsys.readouterr().out


# ---- Docker, runtime requirements, CI, dev scripts ------------------------------------------------------------

def test_dockerfile_is_two_stage_and_secret_free():
    text = _text("Dockerfile")
    assert re.search(r"^FROM node:20\S* AS web", text, re.M)
    assert re.search(r"^FROM python:3\.12-slim", text, re.M)
    for needle in ("npm run build", "requirements-runtime.txt", "requirements-api.txt", "web/dist", "EXPOSE 8000",
                   "src.api.app:create_app", "--factory", "specs/contracts", "data/demo_v4"):
        assert needle in text, needle
    assert re.search(r"^USER\s+\S+", text, re.M), "run as a non-root user"
    assert not re.search(r"^(ENV|ARG)\b.*(PASSWORD|API_KEY|GROQ|GEMINI)", text, re.M | re.I)
    ignore = _text(".dockerignore")
    for needle in (".git", ".venv", ".env", "web/node_modules", "models/"):
        assert needle in ignore, needle


def test_runtime_requirements_are_light_and_pinned():
    pins = {}
    for line in _text("requirements-runtime.txt").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, sep, version = line.partition("==")
            assert sep and version, f"not pinned: {line}"
            pins[name.lower()] = version
    assert {"numpy", "scipy", "networkx", "jsonschema"} <= set(pins)
    assert not set(pins) & {"torch", "sentence-transformers", "streamlit", "google-genai", "chromadb", "gymnasium",
                            "stable-baselines3", "sb3-contrib"}
    main_pins = {}
    for line in _text("requirements.txt").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, _, version = line.partition("==")
            main_pins[name.lower()] = version
    for name, version in pins.items():
        if name in main_pins:
            assert version == main_pins[name], name


def test_ci_runs_web_live_and_docker_jobs():
    text = _text(".github/workflows/ci.yml")
    for needle in ("python -m pytest tests/", "npm ci", "npx tsc --noEmit", "npm run test", "npm run test:e2e",
                   "npm run test:e2e:live", "hashFiles('web/e2e/p34a_live_demo.spec.ts')",
                   "hashFiles('data/demo_v4/demo_trace.json')", "docker build", "scripts/deploy_check.py"):
        assert needle in text, needle
    assert "secrets." not in text


def test_dev_scripts_start_api_and_console():
    for name, flag in (("scripts/dev.ps1", "-Mock"), ("scripts/dev.sh", "--mock")):
        text = _text(name)
        for needle in ("uvicorn", "src.api.app:create_app", "--factory", "npm run dev", "VITE_API_MOCK", flag):
            assert needle in text, (name, needle)
        assert "SENTINEL_DEMO_PASSWORD" not in text and "API_KEY" not in text, name


# ---- Docs -----------------------------------------------------------------------------------------------------

def _banned(text):
    policy = _contract("claims_policy.json")
    banned = [re.compile(p, re.I) for p in policy["banned_outcome_patterns"]]
    exempt = [re.compile(re.escape(p), re.I) for p in policy["negation_exemptions"]]
    return [line for line in text.splitlines()
            if any(b.search(line) for b in banned) and not any(e.search(line) for e in exempt)]


def _evidence_displays():
    """Display strings the Evidence page can show for the frozen files that exist (spec V4_API_SPEC formats)."""
    shown = set()
    for item in _contract("evidence_manifest.json")["items"]:
        path = ROOT / item["path"]
        if not path.is_file():
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        try:
            for part in item["json_pointer"].lstrip("/").split("/"):
                value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        shown |= {f"{value * 100:.1f} %", f"{value * 100:.2f} %", f"{value:.3f}", f"{value:.0f} ms", str(value)}
    return shown


def test_hosting_doc_states_the_disclosure_rule():
    text = _text("docs/HOSTING.md")
    assert DISCLOSURE in text
    for needle in ("SENTINEL_DEMO_PASSWORD", "scripts/deploy_check.py", "docker build", "docker run"):
        assert needle in text, needle
    assert "Render" in text or "Hugging Face" in text


def test_readme_and_legacy_labels():
    readme = _text("README.md")
    assert "## V4 web console" in readme
    for needle in ("scripts/dev.ps1", "docs/HOSTING.md", "DEMO_SCRIPT_V4.md"):
        assert needle in readme, needle
    for name in ("simulation_demo.py", "review_dashboard.py"):
        text = _text(name)
        assert LEGACY_NOTE in text and "st.warning(LEGACY_NOTE)" in text, name


def test_demo_script_v4_is_five_minutes_honest_and_traceable():
    text = _text("DEMO_SCRIPT_V4.md")
    assert text.splitlines()[0] == "Confidential until P0 is filed — do not show outside the project."
    spans = [(int(a) * 60 + int(b), int(c) * 60 + int(d))
             for a, b, c, d in re.findall(r"^## (\d+):(\d\d)–(\d+):(\d\d) \S", text, re.M)]
    assert len(spans) >= 5 and spans[0][0] == 0
    assert all(s < e for s, e in spans) and all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))
    assert spans[-1][1] <= 300
    for needle in (*PAGES, "Run demo", "Live session", "no outcome-effect claim", "21.4 %", "not the evaluated configuration"):
        assert needle in text, needle
    assert _banned(text) == []
    shown = _evidence_displays()
    for token in re.findall(r"\d+(?:\.\d+)? %", text):
        assert token in shown, f"{token} is not a value the Evidence page shows"
