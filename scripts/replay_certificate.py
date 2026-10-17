"""Replay one certificate from its stored inputs.

    python scripts/replay_certificate.py <cert.json> <inputs.json>

Prints MATCH or MISMATCH plus the differing fields; exit code 0 only on MATCH.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.certify.certificate import CertificateInputs  # noqa: E402
from src.certify.replay import replay_certificate  # noqa: E402
from src.geospatial import load_road_graph  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate")
    parser.add_argument("inputs")
    args = parser.parse_args()
    cert = json.loads(Path(args.certificate).read_text(encoding="utf-8"))
    inputs = CertificateInputs.from_dict(json.loads(Path(args.inputs).read_text(encoding="utf-8")))
    report = replay_certificate(cert, inputs, graph=load_road_graph())
    print(report.result, *report.mismatched_fields)
    return 0 if report.result == "MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
