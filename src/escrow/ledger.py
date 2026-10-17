"""Local ledger view and certificate log for one partitioned field team."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from typing import Mapping

from src.certify.ledger import LedgerConflict, SimLedgerAdapter
from src.certify.ledger_view import LedgerView


def believed_state(state_at_cut, left: Mapping[str, int]):
    shelters = tuple(replace(shelter, capacity_reserved=(
        shelter.capacity_total - shelter.occupancy_current - left.get(shelter.shelter_id, 0)))
        for shelter in state_at_cut.shelters)
    return replace(state_at_cut, shelters=shelters)


class _LocalTransaction:
    def __init__(self, adapter: "EscrowLedgerAdapter") -> None:
        self.adapter = adapter
        self.reservations: list[tuple[str, int, str]] = []
        self.releases: list[tuple[str, int, str]] = []
        self.certificate = None

    def reserve(self, shelter_id: str, people: int, cert_id: str) -> None:
        available = self.adapter.left.get(shelter_id, 0) - sum(
            amount for shelter, amount, _ in self.reservations if shelter == shelter_id)
        if people < 0 or people > available:
            raise LedgerConflict(f"{shelter_id}: {people} seats requested; {available} left")
        self.reservations.append((shelter_id, people, cert_id))

    def release(self, shelter_id: str, people: int, cert_id: str) -> None:
        self.releases.append((shelter_id, people, cert_id))

    def append_certificate(self, cert, inputs) -> None:
        self.certificate = (dict(cert), inputs)


class EscrowLedgerAdapter:
    def __init__(self, base: SimLedgerAdapter, team: str, *, cut_view: LedgerView,
                 seats: Mapping[str, int]) -> None:
        self.base, self.team, self.cut_view = base, team, cut_view
        self.seats = dict(seats)
        self.reservations: list[tuple[str, int, str, str]] = []
        self.local_certificates: list[dict] = []
        self.local_inputs: dict[str, object] = {}
        self._next_group = 1
        self._current_group = ""
        prior = base.certificates()
        last = int(prior[-1]["cert_id"].split("-")[1]) if prior else 0
        self._first_cert_number = last + (1 if team == "TEAM-A" else 501)

    @property
    def left(self) -> dict[str, int]:
        used = self.reserved
        return {shelter: max(0, seats - used.get(shelter, 0)) for shelter, seats in self.seats.items()}

    @property
    def reserved(self) -> dict[str, int]:
        used = {shelter: 0 for shelter in self.seats}
        for shelter, people, _, _ in self.reservations:
            used[shelter] += people
        return used

    def view(self) -> LedgerView:
        reserved = {s: self.cut_view.reserved[s] + self.reserved.get(s, 0)
                    for s in self.cut_view.capacity_total}
        capacity = {s: self.cut_view.occupancy[s] + reserved[s] + self.left.get(s, 0)
                    for s in self.cut_view.capacity_total}
        pending = self.cut_view.pending + tuple(
            (group, shelter, people, -1) for shelter, people, _, group in self.reservations)
        return replace(self.cut_view, capacity_total=capacity, reserved=reserved, pending=pending)

    def next_group_id(self) -> str:
        group = f"offline-{self.team}-{self._next_group:04d}"
        self._next_group += 1
        self._current_group = group
        return group

    def next_cert_id(self, prefix: str = "CERT") -> str:
        return f"{prefix}-{self._first_cert_number + len(self.local_certificates):06d}"

    @contextmanager
    def transaction(self):
        tx = _LocalTransaction(self)
        yield tx
        if tx.certificate is None:
            raise LedgerConflict("transaction ended without a certificate")
        for shelter, people, _ in tx.releases:
            remaining = people
            kept = []
            for old_shelter, old_people, cert_id, group in self.reservations:
                if old_shelter == shelter and remaining:
                    released = min(old_people, remaining)
                    old_people -= released
                    remaining -= released
                if old_people:
                    kept.append((old_shelter, old_people, cert_id, group))
            if remaining:
                raise LedgerConflict(f"cannot release {people} at {shelter}")
            self.reservations = kept
        for shelter, people, cert_id in tx.reservations:
            self.reservations.append((shelter, people, cert_id, self._current_group))
        cert, inputs = tx.certificate
        self.local_certificates.append(cert)
        self.local_inputs[cert["cert_id"]] = inputs

    def certificates(self) -> list[dict]:
        return [*self.base.certificates(), *self.local_certificates]

    def inputs(self, cert_id: str):
        return self.local_inputs.get(cert_id) or self.base.inputs(cert_id)
