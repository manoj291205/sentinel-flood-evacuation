"""Prospective dense-index compatibility must include its embedding revision."""

from types import SimpleNamespace

import pytest

from src.rag.ingest import EMBED_MODEL_NAME, EMBED_MODEL_REVISION, EMBEDDING_DIMENSION
from src.rag.retrieve import _validate_dense_collection, frozen_corpus_identity


def collection():
    version, fingerprint = frozen_corpus_identity()
    return SimpleNamespace(count=lambda: 1797, metadata={
        "corpus_version": version, "corpus_fingerprint": fingerprint,
        "embedding_model": EMBED_MODEL_NAME, "embedding_revision": EMBED_MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION, "hnsw:space": "cosine",
    })


def test_complete_matching_embedding_identity_is_accepted():
    _validate_dense_collection(collection())


@pytest.mark.parametrize("field,bad", [("embedding_model", "another-384d-model"),
    ("embedding_revision", "another-revision"), ("embedding_dimension", 256), ("hnsw:space", "l2")])
def test_embedding_identity_mismatch_fails_before_query(field, bad):
    value = collection()
    value.metadata[field] = bad
    with pytest.raises(ValueError, match="embedding|distance"):
        _validate_dense_collection(value)


def test_legacy_index_without_revision_is_explicitly_unverifiable():
    value = collection()
    value.metadata.pop("embedding_revision")
    with pytest.raises(ValueError, match="unverifiable"):
        _validate_dense_collection(value)
