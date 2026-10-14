"""Phase 11 provenance, multi-document ingestion, and compatibility regressions.

Every test uses the committed PDFs and local deterministic fakes.  Nothing downloads a
document or model, so the corpus integrity gate remains runnable in an offline CI job.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from pypdf import PdfReader

from src.constraints.generate import check_grounding
from src.rag import retrieve as retrieval
from src.rag.corpus import (
    ALLOWED_TOPICS,
    CORPUS_VERSION,
    EXCLUDED_SOURCES_PATH,
    MANIFEST_PATH,
    RAW_DOCS_DIR,
    canonical_documents,
    corpus_fingerprint,
    load_manifest,
    sha256_file,
    validate_manifest,
)
from src.rag.ingest import (
    COLLECTION_NAME,
    EMBEDDING_DIMENSION,
    PreparedCorpus,
    build_index,
    prepare_corpus,
)
from src.rag.retrieve import RetrievedChunk

SUMMARY_PATH = Path("data/eval_v3/phase11_corpus_summary.json")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_manifest()


@pytest.fixture(scope="module")
def sources(manifest: dict) -> list[dict]:
    return validate_manifest(manifest)


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


def test_manifest_loads_and_has_frozen_version(manifest: dict):
    assert manifest["schema_version"] == "2.0"
    assert manifest["corpus_version"] == CORPUS_VERSION


def test_at_least_three_canonical_documents_are_retained(sources: list[dict]):
    assert len(sources) == 3


def test_source_ids_are_unique(sources: list[dict]):
    values = [source["source_id"] for source in sources]
    assert len(values) == len(set(values))


def test_canonical_filenames_are_unique(sources: list[dict]):
    values = [source["filename"] for source in sources]
    assert len(values) == len(set(values))


def test_sha_values_are_lowercase_sha256(sources: list[dict]):
    assert all(len(source["sha256"]) == 64 for source in sources)
    assert all(set(source["sha256"]) <= set("0123456789abcdef") for source in sources)


def test_local_files_exist_with_expected_size_and_hash(sources: list[dict]):
    for source in sources:
        path = RAW_DOCS_DIR / source["filename"]
        assert path.is_file()
        assert path.stat().st_size == source["bytes"]
        assert sha256_file(path) == source["sha256"]


def test_duplicate_urls_do_not_count_as_canonical_sources(manifest: dict):
    documents = canonical_documents(manifest)
    url_count = sum(1 + len(source["mirror_urls"]) for source in documents)
    assert url_count > len(documents)
    assert len(documents) == 3


def test_exact_hash_duplicates_are_rejected(manifest: dict):
    duplicate = copy.deepcopy(manifest)
    duplicate["documents"][2]["sha256"] = duplicate["documents"][0]["sha256"]
    duplicate["fingerprint"] = corpus_fingerprint(duplicate["documents"])
    with pytest.raises(ValueError, match="exact-hash duplicates"):
        validate_manifest(duplicate, verify_files=False)


def test_fingerprint_is_deterministic(manifest: dict):
    assert corpus_fingerprint(manifest["documents"]) == corpus_fingerprint(
        manifest["documents"]
    )
    assert corpus_fingerprint(manifest["documents"]) == manifest["fingerprint"]


def test_fingerprint_is_independent_of_manifest_order(manifest: dict):
    assert corpus_fingerprint(reversed(manifest["documents"])) == manifest["fingerprint"]


def test_every_source_has_publisher_and_provenance_url(sources: list[dict]):
    for source in sources:
        assert source["publisher"].strip()
        assert source["url"].startswith("https://")


def test_topics_are_known_and_nonempty(sources: list[dict]):
    for source in sources:
        assert source["topics"]
        assert set(source["topics"]) <= ALLOWED_TOPICS


def test_canonical_pdfs_have_manifest_page_counts(sources: list[dict]):
    for source in sources:
        assert len(PdfReader(RAW_DOCS_DIR / source["filename"]).pages) == source["pages"]
        assert source["pages"] > 0


def test_spot_check_records_are_valid(sources: list[dict]):
    for source in sources:
        assert len(source["spot_checks"]) >= 3
        for check in source["spot_checks"]:
            assert 1 <= check["page"] <= source["pages"]
            assert check["section"].strip()
            assert check["relevance"].strip()


def test_text_extraction_succeeds_for_all_sources(prepared: PreparedCorpus):
    assert prepared.text_page_count == 635
    assert all(count > 0 for count in prepared.source_chunk_counts.values())


def test_chunks_cover_three_sources_with_page_metadata(prepared: PreparedCorpus):
    assert len(prepared.documents) == 1797
    assert len(prepared.source_chunk_counts) == 3
    for metadata in prepared.metadatas:
        assert metadata["source_id"] in prepared.source_chunk_counts
        assert metadata["source_document"].endswith(".pdf")
        assert metadata["page"] > 0
        assert metadata["corpus_version"] == CORPUS_VERSION


def test_extracted_chunks_do_not_contain_nul_artifacts(prepared: PreparedCorpus):
    assert all("\x00" not in text for text in prepared.documents)


class _OfflineEmbeddingModel:
    def encode(self, documents, **_kwargs):
        embeddings = np.ones((len(documents), EMBEDDING_DIMENSION), dtype=np.float32)
        embeddings[:, 0] = np.arange(len(documents), dtype=np.float32) % 17 + 1
        return embeddings


def test_vector_ingestion_succeeds_offline(tmp_path: Path, prepared: PreparedCorpus):
    import chromadb

    chroma_dir = tmp_path / "chroma"
    assert build_index(
        model=_OfflineEmbeddingModel(), chroma_dir=chroma_dir, prepared=prepared
    ) == 0
    collection = chromadb.PersistentClient(path=str(chroma_dir)).get_collection(
        COLLECTION_NAME
    )
    assert collection.count() == len(prepared.documents)
    assert set(collection.get(include=[])["ids"]) == set(prepared.ids)
    assert collection.metadata["corpus_fingerprint"] == load_manifest()["fingerprint"]
    sample = collection.get(limit=10, include=["metadatas"])["metadatas"]
    assert all({"source_id", "source_document", "page"} <= metadata.keys() for metadata in sample)


def test_retrieval_can_return_multiple_source_ids(monkeypatch: pytest.MonkeyPatch):
    class FakeModel:
        def encode(self, _queries, **_kwargs):
            return np.ones((1, EMBEDDING_DIMENSION), dtype=np.float32)

    class FakeCollection:
        metadata = {
            "corpus_version": CORPUS_VERSION,
            "corpus_fingerprint": load_manifest()["fingerprint"],
        }

        def count(self):
            return 1797

        def query(self, **_kwargs):
            return {
                "ids": [["flood-p4-c0", "plan-p8-c0", "shelter-p12-c0"]],
                "documents": [["flood text", "plan text", "shelter text"]],
                "metadatas": [[
                    {"source_document": "flood.pdf", "source_id": "flood", "page": 4},
                    {"source_document": "plan.pdf", "source_id": "plan", "page": 8},
                    {"source_document": "shelter.pdf", "source_id": "shelter", "page": 12},
                ]],
                "distances": [[0.1, 0.2, 0.3]],
            }

    monkeypatch.setattr(retrieval, "_model", lambda: FakeModel())
    monkeypatch.setattr(retrieval, "_collection", lambda: FakeCollection())
    chunks = retrieval.retrieve("evacuation", k=3)
    assert {chunk.source_id for chunk in chunks} == {"flood", "plan", "shelter"}
    assert all(chunk.source_document and chunk.page and chunk.score >= 0 for chunk in chunks)


def test_existing_citation_verifier_accepts_v3_chunk_metadata():
    chunk = RetrievedChunk(
        text="Evacuation routes must remain accessible.",
        source_document="ndma_national_disaster_management_plan_2019.pdf",
        page=306,
        score=0.12,
        source_id="ndma-national-disaster-management-plan-2019",
    )
    payload = {"constraints": [{
        "action_id": "S1",
        "source_excerpt": "evacuation routes must remain accessible",
    }]}
    assert check_grounding(payload, [chunk]) == []
    assert payload["constraints"][0]["citation_verified"] is True


def test_exclusion_log_is_complete_and_reconciled():
    excluded = json.loads(EXCLUDED_SOURCES_PATH.read_text(encoding="utf-8"))
    assert excluded["urls_examined"] == 8
    assert excluded["exact_duplicate_urls"] == 2
    assert excluded["near_duplicate_urls"] == 1
    assert excluded["canonical_documents_retained"] == 3
    assert len(excluded["excluded"]) == 5
    assert all(entry["title"] and entry["url"] and entry["publisher"] for entry in excluded["excluded"])
    assert all(entry["reason"] for entry in excluded["excluded"])


def test_summary_matches_manifest_and_ingestion(manifest: dict, prepared: PreparedCorpus):
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["corpus_version"] == manifest["corpus_version"]
    assert summary["fingerprint"] == manifest["fingerprint"]
    assert summary["canonical_document_count"] == len(canonical_documents(manifest))
    assert summary["page_count"] == prepared.page_count == 652
    assert summary["chunk_count"] == len(prepared.documents) == 1797
    assert summary["embedding_dimension"] == EMBEDDING_DIMENSION
    assert summary["phase10_policy_result_changed"] is False
