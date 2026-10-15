"""Stop statuses must never create a Phase 14C disposition."""

from __future__ import annotations

import socket

import pytest

from scripts import phase14c_run_claim_support as runner
from src.constraints.claim_support import EvidenceChunk
from src.constraints.claim_support_p14c import ProviderResponse, ProviderStop, verify_claim_support_p14c


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Phase 14C provider tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.mark.parametrize(
    ("status", "reason"),
    [(501, "PROVIDER_UNAVAILABLE"), (520, "PROVIDER_UNAVAILABLE"),
     (301, "REQUEST_REJECTED"), (204, "REQUEST_REJECTED")],
)
def test_stop_status_has_no_disposition(monkeypatch, tmp_path, status, reason):
    evidence = EvidenceChunk(
        chunk_id="test", source_id="ndma", filename="ndma.pdf", page=1,
        text="Public flood guidance.", passage_sha256="unused-for-stop",
    )
    transport = lambda request: ProviderResponse(status=status, body={}, headers={})
    with pytest.raises(ProviderStop) as stopped:
        verify_claim_support_p14c("Claim", evidence, transport=transport)
    assert stopped.value.reason == reason
    assert stopped.value.status == status

    monkeypatch.setattr(runner, "_prepared_corpus", lambda: None)
    monkeypatch.setattr(runner, "get_chunk_by_id", lambda *args, **kwargs: evidence)
    result = runner.run(
        transport=transport, out_dir=tmp_path, max_requests=1, zdr_attested=True,
    )
    assert result["stopped_reason"] == reason
    assert result["done"] == 0
    assert result["requests_made"] == 1
    disposition_path = tmp_path / "dispositions.jsonl"
    assert disposition_path.exists()
    assert disposition_path.read_text(encoding="utf-8") == ""
