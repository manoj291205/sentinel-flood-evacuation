"""Third-party replay: regenerate a certificate bit-for-bit from its stored inputs (Phase 25)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.sim.world import get_world_config

from .certificate import CertificateInputs, build_certificate, certificate_hash, edge_set_digest
from .certifier import certify
from .futures import FutureSet, root_key
from .gate import ledger_view_hash
from .params import get_cert_params
from .rollout import HOLD_KEY, rollout_joint


@dataclass(frozen=True)
class ReplayReport:
    result: str  # "MATCH" | "MISMATCH"
    mismatched_fields: tuple[str, ...]


def _diff(a: Any, b: Any, path: str, out: list[str]) -> None:
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        for key in sorted(set(a) | set(b)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in a or key not in b:
                out.append(sub)
            else:
                _diff(a[key], b[key], sub, out)
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            out.append(path)
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(path)


def _never() -> float:
    return 0.0


def replay_certificate(
    cert: Mapping, inputs: CertificateInputs, *, graph,
    futures_factory: Callable[..., Any] | None = None, rollout: Callable = rollout_joint,
) -> ReplayReport:
    if graph.graph_fingerprint != cert.get("graph_fingerprint"):
        return ReplayReport("MISMATCH", ("graph_fingerprint",))
    factory = futures_factory or FutureSet
    world = get_world_config(inputs.world_id)
    params = get_cert_params(inputs.params_id)
    fc = inputs.forecast
    ledger_hash = ledger_view_hash(inputs.ledger)
    root = root_key(
        incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
        graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_hash,
        params_id=params.params_id, backend=params.backend,
    )
    try:
        fs = factory(fc, graph, world, root, inputs.horizon_steps, edge_ids=inputs.edge_ids)
        recorded_looks = cert.get("looks")
        stop = recorded_looks if isinstance(recorded_looks, int) and recorded_looks >= 0 else None
        result = certify(inputs.candidates, fs, inputs.ledger, world, params, graph,
                         clock=_never, rollout=rollout, stop_after_looks=stop)
        # A deadline only changes how many looks completed (replayed above); copy the flag.
        result = dataclasses.replace(result, deadline_hit=bool(cert.get("deadline_hit")))
        key = cert["chosen"]["action_key"]
        chosen = next((c for c in inputs.candidates if c.action_key == key), None)
        if key != HOLD_KEY and chosen is None:
            return ReplayReport("MISMATCH", ("chosen.action_key",))
        kind = cert["kind"]
        if kind in ("DISPATCH", "MIGRATION") and key != result.chosen_key:
            return ReplayReport("MISMATCH", ("chosen.action_key",))
        rebuilt = build_certificate(
            cert_id=cert["cert_id"], kind=kind, incident_id=fc.incident_id,
            scenario_id=cert["scenario_id"], timestep=fc.timestep, root=root,
            forecast_hash=fc.forecast_hash(), graph_fingerprint=graph.graph_fingerprint,
            ledger_hash=ledger_hash, params=params, a_max=result.a_max, result=result,
            candidates=inputs.candidates, chosen_key=key, chosen_people=chosen.people if chosen else 0,
            group_id=cert["chosen"].get("group_id"), operator=cert["operator"],
            commands=cert.get("commands", []), prev_cert_hash=cert.get("prev_cert_hash"),
            edge_set_digest=edge_set_digest(inputs.edge_ids),
        )
    except (ValueError, KeyError) as exc:
        return ReplayReport("MISMATCH", (f"replay_error:{type(exc).__name__}",))
    stored = {k: v for k, v in cert.items() if k != "cert_hash"}
    expected = {k: v for k, v in rebuilt.items() if k != "cert_hash"}
    diffs: list[str] = []
    _diff(stored, expected, "", diffs)
    if not diffs and certificate_hash(cert) != cert.get("cert_hash"):
        diffs.append("cert_hash")
    return ReplayReport("MISMATCH" if diffs else "MATCH", tuple(diffs))
