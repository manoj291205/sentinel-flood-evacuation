"""Provider lifecycle recovery is tested with fake transports only."""

from types import SimpleNamespace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import os
import subprocess

import pytest

from src.constraints.provider_journal import ProviderJournal, ReconciliationRequired


def response(content='{"verdict":"UNSUPPORTED"}'):
    return SimpleNamespace(status=200, body={"choices": [{"message": {
        "content": content, "reasoning": "PRIVATE-REASONING"}}], "model": "fixture"})


def test_issuance_is_durable_before_the_fake_provider_can_run(tmp_path):
    path = tmp_path / "attempts.json"
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        number = journal.begin("P1", {"prompt": "fixture"})
        durable = json.loads(path.read_text(encoding="utf-8"))
        assert durable["requests"][number]["state"] == "ISSUING"
    with pytest.raises(ReconciliationRequired, match="ambiguous"):
        with ProviderJournal(path, {"protocol": "fixture"}, []):
            raise AssertionError("must stop before fake provider")


@pytest.mark.parametrize("stage", ["issued", "response"])
def test_hard_process_exit_preserves_request_reconciliation(tmp_path, stage):
    root = Path(__file__).resolve().parents[1]
    script = '''
from pathlib import Path
from types import SimpleNamespace
import os, sys
from src.constraints.provider_journal import ProviderJournal
directory, stage = Path(sys.argv[1]), sys.argv[2]
with ProviderJournal(directory / 'attempts.json', {'protocol': 'hard-exit-fixture'}, []) as journal:
    index = journal.begin('P1', {'prompt': 'synthetic fixture'})
    (directory / 'fake-provider-entered').write_text('fixture only', encoding='utf-8')
    if stage == 'response':
        journal.resolve(index, SimpleNamespace(status=200, body={'choices': [{'message': {'content': '{"verdict":"UNSUPPORTED"}'}}]}), None)
    os._exit(17)
'''
    process = subprocess.run([sys.executable, "-c", script, str(tmp_path), stage],
                             env={**os.environ, "PYTHONPATH": os.pathsep.join(
                                 (str(root / "scripts/verification"), str(root)))},
                             capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert process.returncode == 17, process.stderr
    assert (tmp_path / "fake-provider-entered").is_file()
    message = "ambiguous" if stage == "issued" else "commit"
    with pytest.raises(ReconciliationRequired, match=message):
        with ProviderJournal(tmp_path / "attempts.json", {"protocol": "hard-exit-fixture"}, []):
            raise AssertionError("an issued request must never be repeated after process death")


def test_known_response_without_disposition_stops_instead_of_repeating(tmp_path):
    path = tmp_path / "attempts.json"
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        number = journal.begin("P1", {"prompt": "fixture"})
        journal.resolve(number, response(), None)
    with pytest.raises(ReconciliationRequired, match="commit"):
        with ProviderJournal(path, {"protocol": "fixture"}, []):
            raise AssertionError("must reconcile the durable response")


def test_committed_disposition_validates_and_provider_reasoning_is_not_saved(tmp_path):
    path = tmp_path / "attempts.json"
    row = {"claim_pair_id": "P1", "verdict": "UNSUPPORTED"}
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        number = journal.begin("P1", {"prompt": "fixture"})
        journal.resolve(number, response(), None)
        journal.commit(row)
    with ProviderJournal(path, {"protocol": "fixture"}, [row]):
        pass
    assert "PRIVATE-REASONING" not in path.read_text(encoding="utf-8")
    with pytest.raises(ReconciliationRequired, match="changed"):
        with ProviderJournal(path, {"protocol": "fixture"}, [{**row, "verdict": "SUPPORTED"}]):
            pass


@pytest.mark.parametrize("status", [429, 503])
def test_known_http_error_is_preserved_and_can_be_retried_explicitly(tmp_path, status):
    path = tmp_path / "attempts.json"
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        number = journal.begin("P1", {})
        journal.resolve(number, SimpleNamespace(status=status, body={}), None)
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        assert len(journal.data["requests"]) == 1
        number = journal.begin("P1", {})
        journal.resolve(number, response(), None)
        journal.commit({"claim_pair_id": "P1", "verdict": "UNSUPPORTED"})
        assert [row["http_status"] for row in journal.data["requests"]] == [status, 200]


def test_network_error_is_ambiguous_and_never_automatically_reissued(tmp_path):
    path = tmp_path / "attempts.json"
    with ProviderJournal(path, {"protocol": "fixture"}, []) as journal:
        number = journal.begin("P1", {})
        journal.resolve(number, None, SimpleNamespace(reason="NETWORK_ERROR", status=None))
    with pytest.raises(ReconciliationRequired, match="ambiguous"):
        with ProviderJournal(path, {"protocol": "fixture"}, []):
            pass


def runner_fixture(monkeypatch, name):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(f"journal_{name}", root / "scripts" / f"{name}.py")
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    text = "A temporary synthetic fixture."
    pair = {"claim_pair_id": "FIXTURE", "claim": "A fixture claim", "chunk_id": "fixture",
            "source_id": "fixture", "filename": "fixture.txt", "page": 1,
            "passage_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    prepared = SimpleNamespace(ids=["fixture"], documents=[text], metadatas=[{
        "source_id": "fixture", "source_document": "fixture.txt", "page": 1}])
    monkeypatch.setattr(runner, "_challenge", lambda *args: ([pair], {"challenge_fingerprint": "f" * 64}))
    monkeypatch.setattr(runner, "_prepared_corpus" if hasattr(runner, "_prepared_corpus") else "prepare_corpus",
                        lambda: prepared)
    return runner


@pytest.mark.parametrize("name", ["phase14c_run_claim_support", "phase14d_run_claim_support"])
def test_actual_runner_never_reissues_after_interrupted_fake_transport(monkeypatch, tmp_path, name):
    runner = runner_fixture(monkeypatch, name)
    calls = []
    class PowerLoss(BaseException):
        pass
    def interrupted(_body):
        calls.append(1)
        raise PowerLoss
    args = {"out_dir": tmp_path, "max_requests": 1, "zdr_attested": True}
    if "14d" in name:
        args.update(challenge_set="practice", prompt_version="14d-prompt-r0")
    with pytest.raises(PowerLoss):
        runner.run(transport=interrupted, **args)
    with pytest.raises(ReconciliationRequired, match="ambiguous"):
        runner.run(transport=interrupted, **args)
    assert len(calls) == 1


@pytest.mark.parametrize("name", ["phase14c_run_claim_support", "phase14d_run_claim_support"])
def test_changed_response_schema_cannot_resume_a_future_run(monkeypatch, tmp_path, name):
    runner = runner_fixture(monkeypatch, name)
    calls = []
    def unavailable(_body):
        calls.append(1)
        return SimpleNamespace(status=503, body={}, headers={})
    args = {"out_dir": tmp_path, "max_requests": 1, "zdr_attested": True}
    if "14d" in name:
        args.update(challenge_set="practice", prompt_version="14d-prompt-r0")
    runner.run(transport=unavailable, **args)
    count = len(calls)
    monkeypatch.setattr(runner, "RESPONSE_SCHEMA", {**runner.RESPONSE_SCHEMA, "title": "changed future schema"})
    with pytest.raises(ReconciliationRequired, match="identity"):
        runner.run(transport=unavailable, **args)
    assert len(calls) == count


def test_superseded_runner_cap_counts_every_fake_generation(monkeypatch, tmp_path):
    runner = runner_fixture(monkeypatch, "phase14b_run_claim_support")
    calls = []
    def malformed(_prompt):
        calls.append(1)
        return "not JSON"
    result = runner.run(max_requests=1, client=malformed, ledger_path=tmp_path / "dispositions.jsonl")
    assert len(calls) == result["requests_made"] == 1
    assert result["done"] == 0 and result["stopped_reason"] == "MAX_REQUESTS"


def test_superseded_cli_does_not_default_to_gemini(monkeypatch, capsys):
    runner = runner_fixture(monkeypatch, "phase14b_run_claim_support")
    monkeypatch.setattr(sys, "argv", ["phase14b_run_claim_support.py"])
    assert runner.main() == 2
    assert "live execution is disabled" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["phase14c_run_claim_support", "phase14d_run_claim_support"])
def test_nonfinite_provider_data_keeps_frozen_parse_retry_and_valid_json_journal(monkeypatch, tmp_path, name):
    runner = runner_fixture(monkeypatch, name)
    spans_key = "supporting_sentence_ids" if "14d" in name else "supporting_spans"
    def reply(confidence):
        content = {"verdict": "UNSUPPORTED", "confidence": confidence,
                   spans_key: [], "reason": "Temporary test response"}
        return SimpleNamespace(status=200, headers={"authorization": "PRIVATE-HEADER"}, body={
            "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
            "usage": {"total_tokens": float("nan")}, "model": "fixture"})
    replies = iter([reply(float("nan")), reply(.1)])
    args = {"out_dir": tmp_path, "max_requests": 2, "zdr_attested": True}
    if "14d" in name:
        args.update(challenge_set="practice", prompt_version="14d-prompt-r0")
    result = runner.run(transport=lambda body: next(replies), **args)
    assert result["done"] == 1 and result["requests_made"] == 2
    raw = (tmp_path / "attempt_journal.json").read_text(encoding="utf-8")
    durable = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert "normalized_content" not in durable["requests"][0]
    assert durable["requests"][1]["normalized_content"]["confidence"] == .1
    assert "PRIVATE-HEADER" not in raw and "NaN" not in raw
