"""Separate diagnostic contract; never substitutes for strict trace reconstruction."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import json

from src.certify.certificate import CertificateInputs

CONTRACT_VERSION = "sentinel-trace-portability-v1"


@dataclass(frozen=True)
class PortabilityReport:
    contract_version: str
    strict_equal: bool
    hash_equivalent: bool
    raw_difference_paths: tuple[str, ...]
    incompatible_paths: tuple[str, ...]


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = f"{path}/{key}"
            if key not in a or key not in b:
                yield sub
            else:
                yield from _differences(a[key], b[key], sub)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield path
        for index, (left, right) in enumerate(zip(a, b)):
            yield from _differences(left, right, f"{path}/{index}")
    elif _json(a) != _json(b):
        yield path


def compare_trace_portability(rebuilt: dict, recorded: dict) -> PortabilityReport:
    """Require exact trace fields except raw hazards with the SAME registered forecast hash.

    The existing forecast_hash contract rounds at nine decimals. This adds no new
    tolerance and grants no execution/citation permission. V2 inputs digests and all
    certificate fields remain exact, so operational integrity is not weakened.
    """
    raw = tuple(_differences(rebuilt, recorded))
    normalized = copy.deepcopy(rebuilt)
    for cert_id in set(rebuilt.get("inputs", {})) & set(recorded.get("inputs", {})):
        left, right = rebuilt["inputs"][cert_id], recorded["inputs"][cert_id]
        try:
            first, second = CertificateInputs.from_dict(left), CertificateInputs.from_dict(right)
            if first.forecast.forecast_hash() != second.forecast.forecast_hash():
                continue
            for field in ("zone_severity", "shelter_severity"):
                normalized["inputs"][cert_id]["forecast"][field] = copy.deepcopy(right["forecast"][field])
        except (KeyError, TypeError, ValueError):
            continue
    incompatible = tuple(_differences(normalized, recorded))
    return PortabilityReport(CONTRACT_VERSION, not raw, not incompatible, raw, incompatible)
