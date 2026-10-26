"""Vehicle / shelter-admission commands; each names the certificate that authorizes it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Union


@dataclass(frozen=True)
class VehicleCommand:
    cert_id: str
    cert_hash: str
    group_id: str | None
    zone_id: str
    shelter_id: str
    people: int
    edge_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionCommand:
    cert_id: str
    cert_hash: str
    shelter_id: str
    people: int
    group_id: str | None


@dataclass(frozen=True)
class RerouteCommand:
    cert_id: str
    cert_hash: str
    group_id: str
    shelter_id: str
    edge_ids: tuple[str, ...]


Command = Union[VehicleCommand, AdmissionCommand, RerouteCommand]


class CommandSink(Protocol):
    def send(self, command: Command) -> None: ...


class InMemorySink:
    def __init__(self) -> None:
        self.sent: list[Command] = []

    def send(self, command: Command) -> None:
        self.sent.append(command)


_ACTUATING_KINDS = {"DISPATCH", "MIGRATION", "OVERRIDE"}


def authorize(command: Command, ledger) -> bool:
    """True iff a valid, actuating certificate in the ledger matches the command exactly."""
    from src.certify.certificate import (
        BOUND_CERT_VERSION, CertificateError, certificate_inputs_digest,
        edge_set_digest, validate_certificate,
    )
    from src.certify.gate import ledger_view_hash

    if not isinstance(command, (VehicleCommand, AdmissionCommand, RerouteCommand)):
        return False
    cert = next((c for c in ledger.certificates() if c.get("cert_id") == command.cert_id), None)
    if cert is None:
        return False
    try:
        validate_certificate(cert)
    except (CertificateError, TypeError, ValueError):
        return False
    if (cert["cert_version"] != BOUND_CERT_VERSION
            or cert["kind"] not in _ACTUATING_KINDS or cert["cert_hash"] != command.cert_hash):
        return False
    chosen = cert["chosen"]
    if command.group_id != chosen["group_id"]:
        return False
    try:
        inputs = ledger.inputs(command.cert_id)
        candidate = next(c for c in inputs.candidates if c.action_key == chosen["action_key"])
        certified = [c for c in cert["candidates"] if c["action_key"] == chosen["action_key"]]
        if (inputs.cert_id != cert["cert_id"]
                or certificate_inputs_digest(inputs) != cert["inputs_digest"]
                or inputs.params_id != cert["params"]["params_id"]
                or inputs.forecast.forecast_hash() != cert["forecast_hash"]
                or inputs.forecast.graph_fingerprint != cert["graph_fingerprint"]
                or ledger_view_hash(inputs.ledger) != cert["ledger_hash"]
                or edge_set_digest(inputs.edge_ids) != cert.get("edge_set_digest")
                or candidate.people != chosen["people"]
                or len(certified) != 1 or certified[0]["verdict"] != "FEASIBLE"
                or certified[0]["people"] != candidate.people
                or certified[0]["zone_id"] != candidate.zone_id
                or certified[0]["shelter_id"] != candidate.shelter_id
                or not set(candidate.edge_ids) <= set(inputs.edge_ids)):
            return False
    except (AttributeError, KeyError, StopIteration, TypeError, ValueError):
        return False
    if isinstance(command, RerouteCommand):
        return (cert["kind"] == "MIGRATION" and candidate.shelter_id == command.shelter_id
                and tuple(command.edge_ids) == candidate.edge_ids)
    if chosen["people"] != command.people or "->" not in chosen["action_key"]:
        return False
    zone, shelter = chosen["action_key"].split("->", 1)
    if shelter != command.shelter_id:
        return False
    if isinstance(command, VehicleCommand):
        return (cert["kind"] in {"DISPATCH", "OVERRIDE"} and zone == command.zone_id
                and tuple(command.edge_ids) == candidate.edge_ids)
    return True
