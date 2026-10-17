"""Hash-chained dispatch certificate (Phase 25, confidential core element E)."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

from .certifier import CertificationResult
from .forecast import ForecastSnapshot
from .ledger_view import LedgerView
from .params import CertParams
from .rollout import HOLD_KEY, Candidate

CERT_VERSION = "sentinel-cert-v1"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "specs" / "contracts" / "certificate.schema.json"


class CertificateError(ValueError):
    pass


def canonical_json(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def certificate_hash(cert: Mapping) -> str:
    return hashlib.sha256(canonical_json({k: v for k, v in cert.items() if k != "cert_hash"})).hexdigest()


def edge_set_digest(edge_ids: Sequence[str]) -> str:
    """Same rule as ``FutureSet.edge_set_digest`` for a restricted edge set."""
    return hashlib.sha256("\n".join(sorted(set(edge_ids))).encode("utf-8")).hexdigest()


def build_certificate(
    *, cert_id: str, kind: str, incident_id: str, scenario_id: str, timestep: int, root: str,
    forecast_hash: str, graph_fingerprint: str, ledger_hash: str, params: CertParams, a_max: int,
    result: CertificationResult | None, candidates: Sequence[Candidate], chosen_key: str,
    chosen_people: int, group_id: str | None, operator: Mapping[str, str],
    commands: Sequence[Mapping[str, str]], prev_cert_hash: str | None, edge_set_digest: str,
) -> dict:
    by_key = {c.action_key: c for c in candidates}
    entries = []
    if result is not None and result.candidates:
        for cc in result.candidates:
            cand = by_key[cc.action_key]
            entries.append({
                "action_key": cc.action_key, "zone_id": cand.zone_id, "shelter_id": cand.shelter_id,
                "people": cand.people, "verdict": cc.verdict.value, "successes": cc.successes,
                "n": cc.n, "lower": round(cc.lower, 12), "upper": round(cc.upper, 12),
                "mean_utility": round(cc.mean_utility, 9),
                "outcome_counts": {k: int(v) for k, v in cc.outcome_counts.items() if k != "POLICY"},
            })
        entries.append({
            "action_key": HOLD_KEY, "zone_id": None, "shelter_id": None, "people": 0,
            "verdict": "ALWAYS_ALLOWED", "successes": 0, "n": 0, "lower": None, "upper": None,
            "mean_utility": 0.0, "outcome_counts": {},
        })
    cert = {
        "cert_id": cert_id, "cert_version": CERT_VERSION, "kind": kind, "incident_id": incident_id,
        "scenario_id": scenario_id, "timestep": timestep, "root_key": root,
        "forecast_hash": forecast_hash, "graph_fingerprint": graph_fingerprint,
        "ledger_hash": ledger_hash,
        "params": {
            "params_id": params.params_id, "eps_dispatch": params.eps_dispatch,
            "eps_keep": params.eps_keep, "delta": params.delta, "k0": params.k0,
            "max_looks": params.max_looks, "a_max": a_max, "deadline_ms": min(params.deadline_ms, sys.float_info.max),
            "backend": params.backend,
        },
        "edge_set_digest": edge_set_digest,
        "futures_used": result.n_final if result is not None else 0,
        "looks": result.looks if result is not None else 0,
        "deadline_hit": result.deadline_hit if result is not None else False,
        "candidates": entries,
        "chosen": {"action_key": chosen_key, "people": chosen_people, "group_id": group_id},
        "operator": dict(operator),
        "commands": [dict(c) for c in commands],
        "prev_cert_hash": prev_cert_hash,
    }
    cert["cert_hash"] = certificate_hash(cert)
    return cert


@lru_cache(maxsize=1)
def _validator():
    import jsonschema

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def validate_certificate(cert: Mapping) -> None:
    errors = sorted(_validator().iter_errors(cert), key=lambda e: list(e.path))
    if errors:
        raise CertificateError(f"schema: {errors[0].message} at {list(errors[0].path)}")
    if certificate_hash(cert) != cert["cert_hash"]:
        raise CertificateError("cert_hash does not match the certificate content")


def verify_chain(certs: Sequence[Mapping]) -> int | None:
    """Index of the first broken link (bad hash or wrong ``prev_cert_hash``), None if intact."""
    for i, cert in enumerate(certs):
        if certificate_hash(cert) != cert["cert_hash"]:
            return i
        if i > 0 and cert["prev_cert_hash"] != certs[i - 1]["cert_hash"]:
            return i
    return None


@dataclass(frozen=True)
class CertificateInputs:
    """Everything replay needs, stored next to every certificate."""

    cert_id: str
    world_id: str
    params_id: str
    horizon_steps: int
    forecast: ForecastSnapshot
    ledger: LedgerView
    candidates: tuple[Candidate, ...]
    edge_ids: tuple[str, ...]

    def to_dict(self) -> dict:
        f = self.forecast
        lv = self.ledger
        return {
            "cert_id": self.cert_id, "world_id": self.world_id, "params_id": self.params_id,
            "horizon_steps": self.horizon_steps,
            "forecast": {
                "incident_id": f.incident_id, "timestep": f.timestep,
                "timestep_minutes": f.timestep_minutes,
                "uncertainty_config_id": f.uncertainty_config_id,
                "zone_severity": [list(x) for x in f.zone_severity],
                "zone_trend": [list(x) for x in f.zone_trend],
                "shelter_severity": [list(x) for x in f.shelter_severity],
                "shelter_status": [list(x) for x in f.shelter_status],
                "edge_open": [list(x) for x in f.edge_open],
                "regional_shock_estimate": f.regional_shock_estimate,
                "graph_fingerprint": f.graph_fingerprint,
            },
            "ledger": {
                "timestep": lv.timestep, "capacity_total": dict(lv.capacity_total),
                "occupancy": dict(lv.occupancy), "reserved": dict(lv.reserved),
                "pending": [list(p) for p in lv.pending],
                "occupancy_sigma": dict(lv.occupancy_sigma),
                "occupancy_age_s": dict(lv.occupancy_age_s),
            },
            "candidates": [
                {"zone_id": c.zone_id, "shelter_id": c.shelter_id, "people": c.people,
                 "edge_ids": list(c.edge_ids), "departure_timestep": c.departure_timestep,
                 "start_minutes": c.start_minutes}
                for c in self.candidates
            ],
            "edge_ids": list(self.edge_ids),
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> "CertificateInputs":
        f, lv = d["forecast"], d["ledger"]

        def pairs(rows):
            return tuple(tuple(r) for r in rows)

        forecast = ForecastSnapshot(
            incident_id=f["incident_id"], timestep=f["timestep"],
            timestep_minutes=f["timestep_minutes"],
            uncertainty_config_id=f["uncertainty_config_id"],
            zone_severity=pairs(f["zone_severity"]), zone_trend=pairs(f["zone_trend"]),
            shelter_severity=pairs(f["shelter_severity"]), shelter_status=pairs(f["shelter_status"]),
            edge_open=pairs(f["edge_open"]),
            regional_shock_estimate=f["regional_shock_estimate"],
            graph_fingerprint=f["graph_fingerprint"],
        )
        ledger = LedgerView(
            timestep=lv["timestep"], capacity_total=dict(lv["capacity_total"]),
            occupancy=dict(lv["occupancy"]), reserved=dict(lv["reserved"]),
            pending=pairs(lv["pending"]), occupancy_sigma=dict(lv["occupancy_sigma"]),
            occupancy_age_s=dict(lv["occupancy_age_s"]),
        )
        candidates = tuple(
            Candidate(c["zone_id"], c["shelter_id"], c["people"], tuple(c["edge_ids"]),
                      c["departure_timestep"], c.get("start_minutes"))
            for c in d["candidates"]
        )
        return cls(d["cert_id"], d["world_id"], d["params_id"], d["horizon_steps"], forecast,
                   ledger, candidates, tuple(d["edge_ids"]))
