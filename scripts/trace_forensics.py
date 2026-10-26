"""Read-only six-step demo diagnostics. Does not write traces or run research evaluations."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]


def reference_cos(angle: float, precision: int = 100) -> float:
    """Independent high-precision diagnostic on the Box–Muller [0, 2π] domain."""
    if not math.isfinite(angle) or not 0 <= angle <= 2 * math.pi:
        raise ValueError("diagnostic cosine expects a Box–Muller angle")
    with localcontext() as context:
        context.prec = precision
        context.rounding = ROUND_HALF_EVEN
        square = Decimal.from_float(angle) ** 2
        term = total = Decimal(1)
        for index in range(1, 512):
            term = -term * square / Decimal((2 * index - 1) * (2 * index))
            updated = total + term
            if updated == total:
                return float(updated)
            total = updated
    raise ArithmeticError("reference cosine did not converge")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--reference-cos", action="store_true",
                        help="also reconstruct with a process-only diagnostic reference; never changes production RNG")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))
    from src.api.demo_live import build_demo_trace, load_demo_trace, TRACE_PATH
    from src.sim.randomness import EpisodeRandomStreams
    # Keep the diagnostic comparator from this branch when inspecting baseline source.
    import importlib.util
    spec = importlib.util.spec_from_file_location("trace_portability_diagnostic", ROOT / "src/api/trace_portability.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    recorded, rebuilt = load_demo_trace(), build_demo_trace()
    report = module.compare_trace_portability(rebuilt, recorded)
    output = {"contract": report.contract_version, "python": sys.version,
              "platform": platform.platform(), "source_root": str(args.source_root.resolve()),
              "artifact_sha256": hashlib.sha256(TRACE_PATH.read_bytes()).hexdigest(),
              "default": asdict(report), "raw_values": []}
    for path in report.raw_difference_paths:
        left, right = rebuilt, recorded
        for key in path.strip("/").split("/"):
            left = left[int(key)] if isinstance(left, list) else left[key]
            right = right[int(key)] if isinstance(right, list) else right[key]
        output["raw_values"].append({"path": path, "rebuilt": left, "recorded": right,
            "rebuilt_hex": left.hex() if isinstance(left, float) else None,
            "recorded_hex": right.hex() if isinstance(right, float) else None})
    if args.reference_cos:
        original = EpisodeRandomStreams.normal
        def reference(self, stream, *key):
            first = int.from_bytes(self._digest(stream, key, 0)[:8], "big")
            second = int.from_bytes(self._digest(stream, key, 1)[:8], "big")
            u1, u2 = (first + 1) / (2**64 + 1), (second + 1) / (2**64 + 1)
            return math.sqrt(-2 * math.log(u1)) * reference_cos(2 * math.pi * u2)
        try:
            EpisodeRandomStreams.normal = reference
            diagnostic = build_demo_trace()
        finally:
            EpisodeRandomStreams.normal = original
        output["reference_cos_diagnostic_only"] = asdict(module.compare_trace_portability(diagnostic, recorded))
    print(json.dumps(output, indent=2, allow_nan=False))
    return 0  # Diagnostic completion, NOT the strict reconstruction test's exit status.


if __name__ == "__main__":
    raise SystemExit(main())
