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
    from src.certify.certificate import CertificateError, validate_certificate

    cert = next((c for c in ledger.certificates() if c.get("cert_id") == command.cert_id), None)
    if cert is None:
        return False
    try:
        validate_certificate(cert)
    except CertificateError:
        return False
    if cert["kind"] not in _ACTUATING_KINDS or cert["cert_hash"] != command.cert_hash:
        return False
    chosen = cert["chosen"]
    if isinstance(command, RerouteCommand):
        return (cert["kind"] == "MIGRATION" and chosen["group_id"] == command.group_id
                and chosen["action_key"].endswith("->" + command.shelter_id))
    if chosen["people"] != command.people or "->" not in chosen["action_key"]:
        return False
    zone, shelter = chosen["action_key"].split("->", 1)
    if shelter != command.shelter_id:
        return False
    if isinstance(command, VehicleCommand) and zone != command.zone_id:
        return False
    return True
