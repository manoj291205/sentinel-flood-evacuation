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


_REGISTRY = {"v4-cert-v1": CertParams()}


def get_cert_params(params_id: str) -> CertParams:
    try:
        return _REGISTRY[params_id]
    except KeyError as exc:
        raise ValueError(f"unknown certification params {params_id!r}; choose {sorted(_REGISTRY)}") from exc
