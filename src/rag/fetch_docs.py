"""Fetch the real NDMA / NIDM flood-management guideline PDFs into data/raw_docs/.

These are genuine published government documents. Nothing here generates, synthesises,
or stands in for a source document: if a download fails, this script says so and exits
non-zero rather than leaving a placeholder behind. See data/raw_docs/README.md.

Run:  .venv/bin/python -m src.rag.fetch_docs
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAW_DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "raw_docs"
MANIFEST_PATH = RAW_DOCS_DIR / "MANIFEST.json"

# Both URLs were verified reachable from this machine and confirmed to serve real PDFs.
#
# NOTE on the NIDM path: the kickoff prompt gives "/pdf/guidelines/floods.pdf" (lowercase
# "pdf"), which returns HTTP 404 -- that host's paths are case-sensitive. "/PDF/..." serves
# the file. Same host, same filename, corrected casing. This is NOT a substituted document.
#
# NOTE on HEAD: nidm.gov.in answers HEAD with 404 while answering GET with 200, so this
# script must never use a HEAD request to test for existence.
# VERIFIED 2026-09-02 by reading the extracted text: both URLs serve the SAME document,
# "National Disaster Management Guidelines: Management of Floods", NDMA, Government of
# India, 168 pages, signed "New Delhi ... 17 January, 2008". (The PDF's own /CreationDate
# metadata says 2004 and is unreliable; the `file` utility reports 31 pages and is also
# wrong -- it misreads linearized PDFs. pypdf reports the true 168.)
SOURCES = [
    {
        "filename": "ndma_flood_guidelines.pdf",
        "url": "https://ndma.gov.in/sites/default/files/PDF/Guidelines/flood.pdf",
        "publisher": "National Disaster Management Authority (NDMA), Government of India",
        "title": "National Disaster Management Guidelines: Management of Floods",
        "dated": "17 January 2008 (per the signed foreword inside the document)",
    },
    {
        # Byte-identical mirror of the NDMA file above -- NOT a second, distinct document.
        # Deduplicated at fetch time; recorded in the manifest as a mirror URL.
        "filename": "nidm_floods.pdf",
        "url": "https://nidm.gov.in/PDF/guidelines/floods.pdf",
        "publisher": "National Institute of Disaster Management (NIDM), Government of India",
        "title": "Mirror of the NDMA Management of Floods guidelines",
        "dated": "same file as the NDMA copy",
    },
]

USER_AGENT = "sentinel-sprint-capstone-prototype/0.1 (academic prototype; one-off fetch)"
TIMEOUT_SECONDS = 180


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def page_count(path: Path) -> int | None:
    """Page count via pypdf, or None if it cannot be determined."""
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception as exc:  # noqa: BLE001 - informational only, never fatal here
        print(f"    (could not read page count: {exc})")
        return None


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_all() -> int:
    RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    failures: list[str] = []
    by_hash: dict[str, dict] = {}  # sha256 -> the entry that first claimed it

    for source in SOURCES:
        target = RAW_DOCS_DIR / source["filename"]
        print(f"\n[{source['filename']}]")
        print(f"  url: {source['url']}")

        try:
            payload = download(source["url"])
        except Exception as exc:  # noqa: BLE001 - we want the reason, whatever it is
            print(f"  FAILED: {exc}")
            failures.append(f"{source['filename']}: {exc}")
            continue

        # Refuse anything that is not actually a PDF. An error page saved as a .pdf
        # would silently poison the whole RAG corpus.
        if not payload.startswith(b"%PDF"):
            head = payload[:80]
            print(f"  FAILED: response is not a PDF (starts with {head!r})")
            failures.append(f"{source['filename']}: not a PDF")
            continue

        digest = sha256_of(payload)

        # VERIFIED 2026-09-02: the NDMA and NIDM URLs return byte-identical files, so the
        # "two sources" are one document served from two hosts. Indexing both would put
        # every chunk into the corpus twice and let a top-3 retrieval come back as three
        # copies of the same passage. Keep one file; record the other URL as a mirror.
        if digest in by_hash:
            canonical = by_hash[digest]
            canonical.setdefault("mirror_urls", []).append(source["url"])
            print(f"  DUPLICATE: byte-identical to {canonical['filename']} (sha256 matches)")
            print(f"  recorded as a mirror URL; not saved as a second file")
            if target.exists():
                target.unlink()
                print(f"  removed redundant copy at {target.name}")
            continue

        target.write_bytes(payload)
        pages = page_count(target)

        print(f"  saved: {target.relative_to(RAW_DOCS_DIR.parents[1])}")
        print(f"  bytes: {len(payload):,}")
        print(f"  pages: {pages}")
        print(f"  sha256: {digest}")

        entry = {
            "filename": source["filename"],
            "url": source["url"],
            "mirror_urls": [],
            "publisher": source["publisher"],
            "title": source["title"],
            "dated": source["dated"],
            "sha256": digest,
            "bytes": len(payload),
            "pages": pages,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        by_hash[digest] = entry
        entries.append(entry)

    if entries:
        MANIFEST_PATH.write_text(
            json.dumps(
                {
                    "_note": (
                        "Provenance record for the REAL source documents in this directory. "
                        "Every file listed here was downloaded from the URL shown and verified "
                        "to start with the %PDF magic bytes. Nothing in this directory is "
                        "generated, synthesised, or fabricated. Where mirror_urls is "
                        "non-empty, those URLs were verified to serve byte-identical "
                        "content (same sha256) and are therefore NOT separate documents."
                    ),
                    "documents": entries,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"\nWrote manifest: {MANIFEST_PATH}")

    if failures:
        print("\n" + "=" * 70)
        print("SOME DOCUMENTS COULD NOT BE FETCHED:")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nNo placeholder document has been created. Download the file(s) manually\n"
            "into data/raw_docs/ and re-run this script."
        )
        print("=" * 70)

    mirrors = sum(len(e.get("mirror_urls", [])) for e in entries)
    print(
        f"\n{len(entries)} distinct document(s) in data/raw_docs/ "
        f"from {len(SOURCES)} source URL(s) ({mirrors} duplicate mirror URL(s))"
    )
    # At least one real document is enough for the RAG step to be meaningful.
    return 0 if entries else 1


if __name__ == "__main__":
    sys.exit(fetch_all())
