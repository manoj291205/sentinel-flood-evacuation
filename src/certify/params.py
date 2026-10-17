"""Certification parameters (confidential). ``get_cert_params`` is added in Phase 24."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CertParams:
    params_id: str = "v4-cert-v1"
    eps_dispatch: float = 0.05
    eps_keep: float = 0.10
    delta: float = 0.01
    k0: int = 256
    max_looks: int = 4
    deadline_ms: float = 30_000.0
    theta_unsafe: float = 0.70
    k_sigma: float = 2.0
    age_scale_s: float = 30.0
    w_strand: float = 1.0
    w_unsafe: float = 1.5
    w_overflow: float = 0.5
    backend: str = "sha256"


_REGISTRY = {
    "v4-cert-v1": CertParams(),
    # CI speed only; never used for results.
    "v4-cert-test-v1": CertParams(
        params_id="v4-cert-test-v1", eps_dispatch=0.30, eps_keep=0.40, k0=32, max_looks=2,
        deadline_ms=600_000.0,
    ),
}


def get_cert_params(params_id: str) -> CertParams:
    try:
        return _REGISTRY[params_id]
    except KeyError as exc:
        raise ValueError(f"unknown certification params {params_id!r}; choose {sorted(_REGISTRY)}") from exc
