"""Re-fetch the frozen authoritative corpus with strict provenance checks.

Normal ingestion and retrieval are offline. This module is the intentional online
maintenance path; it refuses non-PDF responses, changed bytes, and canonical duplicates.

Run:  .venv/bin/python -m src.rag.fetch_docs
"""

from __future__ import annotations

import sys
import urllib.request

from .corpus import RAW_DOCS_DIR, load_manifest, sha256_file, validate_manifest

USER_AGENT = "sentinel-sprint-capstone-prototype/0.1 (academic corpus maintenance)"
TIMEOUT_SECONDS = 180


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def _verified_payload(url: str, expected_sha256: str) -> bytes:
    payload = download(url)
    if not payload.startswith(b"%PDF"):
        raise ValueError(f"response from {url} is not a PDF")
    import hashlib

    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"upstream bytes changed for {url}: expected {expected_sha256}, got {actual}; "
            "review and version the source intentionally"
        )
    return payload


def fetch_all() -> int:
    manifest = load_manifest()
    documents = validate_manifest(manifest, verify_files=False)
    expected_hashes = [item["sha256"] for item in documents]
    if len(expected_hashes) != len(set(expected_hashes)):
        raise ValueError("two canonical registry entries have the same expected SHA-256")

    failures: list[str] = []
    mirror_count = 0
    for document in documents:
        target = RAW_DOCS_DIR / document["filename"]
        print(f"\n[{document['source_id']}]\n  canonical: {document['url']}")
        try:
            payload = _verified_payload(document["url"], document["sha256"])
            target.write_bytes(payload)
            print(f"  saved {target.name}: {len(payload):,} bytes")
            for mirror_url in document.get("mirror_urls", []):
                mirror = _verified_payload(mirror_url, document["sha256"])
                if mirror != payload:
                    raise ValueError(f"mirror content mismatch despite hash check: {mirror_url}")
                mirror_count += 1
                print(f"  verified byte-identical mirror: {mirror_url}")
        except Exception as exc:  # noqa: BLE001 - preserve the exact remote failure
            failures.append(f"{document['source_id']}: {exc}")
            print(f"  FAILED: {exc}")

    if failures:
        print("\nCorpus fetch failed; no manifest or expected hash was silently changed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    validate_manifest(manifest)
    for document in documents:
        path = RAW_DOCS_DIR / document["filename"]
        print(f"  verified local SHA-256: {sha256_file(path)}  {path.name}")
    print(
        f"\nVerified {len(documents)} distinct canonical document(s) and "
        f"{mirror_count} duplicate mirror URL(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(fetch_all())
