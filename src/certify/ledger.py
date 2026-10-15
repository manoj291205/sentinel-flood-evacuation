"""Capacity ledger with all-or-nothing reserve + certificate transactions (Phase 25)."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, ContextManager, Iterator, Mapping, Protocol

from .certificate import CertificateInputs
from .ledger_view import LedgerView, ledger_view_from_state


class LedgerConflict(RuntimeError):
    """A reservation would exceed capacity (or the simulator refused the action)."""


class LedgerTx(Protocol):
    def reserve(self, shelter_id: str, people: int, cert_id: str) -> None: ...
    def release(self, shelter_id: str, people: int, cert_id: str) -> None: ...
    def append_certificate(self, cert: Mapping, inputs: CertificateInputs) -> None: ...


class Ledger(Protocol):
    def view(self) -> LedgerView: ...
    def transaction(self) -> ContextManager[LedgerTx]: ...
    def certificates(self) -> list[dict]: ...
    def inputs(self, cert_id: str) -> CertificateInputs: ...
    def next_cert_id(self, prefix: str = "CERT") -> str: ...


def _next_id(existing: list[str], prefix: str) -> str:
    numbers = [int(i.split("-")[1]) for i in existing if i.startswith(prefix + "-")]
    return f"{prefix}-{max(numbers, default=0) + 1:06d}"


class _SqliteTx:
    def __init__(self, ledger: "SqliteLedger") -> None:
        self._l = ledger

    def reserve(self, shelter_id: str, people: int, cert_id: str) -> None:
        conn = self._l._conn
        row = conn.execute(
            "SELECT capacity, occupancy FROM shelters WHERE shelter_id=?", (shelter_id,)
        ).fetchone()
        if row is None:
            raise LedgerConflict(f"unknown shelter {shelter_id}")
        reserved = conn.execute(
            "SELECT COALESCE(SUM(people),0) FROM reservations WHERE shelter_id=?", (shelter_id,)
        ).fetchone()[0]
        if row[1] + reserved + people > row[0]:
            raise LedgerConflict(
                f"{shelter_id}: occupancy {row[1]} + reserved {reserved} + {people} exceeds {row[0]}"
            )
        conn.execute(
            "INSERT INTO reservations (cert_id, shelter_id, people) VALUES (?,?,?)",
            (cert_id, shelter_id, people),
        )
        self._l._hook("after_reserve")

    def release(self, shelter_id: str, people: int, cert_id: str) -> None:
        conn = self._l._conn
        row = conn.execute(
            "SELECT rowid, people FROM reservations WHERE shelter_id=? AND people>=? ORDER BY rowid LIMIT 1",
            (shelter_id, people),
        ).fetchone()
        if row is None:
            raise LedgerConflict(f"no reservation of {people} at {shelter_id} to release")
        if row[1] == people:
            conn.execute("DELETE FROM reservations WHERE rowid=?", (row[0],))
        else:
            conn.execute("UPDATE reservations SET people=people-? WHERE rowid=?", (people, row[0]))

    def append_certificate(self, cert: Mapping, inputs: CertificateInputs) -> None:
        self._l._conn.execute(
            "INSERT INTO certificates (cert_id, cert_json, inputs_json) VALUES (?,?,?)",
            (cert["cert_id"], json.dumps(cert, sort_keys=True), json.dumps(inputs.to_dict(), sort_keys=True)),
        )
        self._l._hook("after_certificate")


class SqliteLedger:
    """Thread-safe SQLite ledger; one writer at a time (``BEGIN IMMEDIATE``)."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        shelters: Mapping[str, tuple[int, int]] = {},
        fail_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._lock = threading.RLock()
        self._fail_hook = fail_hook
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS shelters (shelter_id TEXT PRIMARY KEY, capacity INTEGER, occupancy INTEGER);
            CREATE TABLE IF NOT EXISTS reservations (cert_id TEXT, shelter_id TEXT, people INTEGER);
            CREATE TABLE IF NOT EXISTS certificates (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, cert_id TEXT UNIQUE, cert_json TEXT, inputs_json TEXT);
            """
        )
        for sid, (capacity, occupancy) in shelters.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO shelters (shelter_id, capacity, occupancy) VALUES (?,?,?)",
                (sid, capacity, occupancy),
            )

    def _hook(self, stage: str) -> None:
        if self._fail_hook is not None:
            self._fail_hook(stage)

    def view(self, timestep: int = 0) -> LedgerView:
        with self._lock:
            rows = self._conn.execute("SELECT shelter_id, capacity, occupancy FROM shelters").fetchall()
            reserved = {sid: 0 for sid, _, _ in rows}
            pending = []
            for cert_id, sid, people in self._conn.execute(
                "SELECT cert_id, shelter_id, people FROM reservations ORDER BY rowid"
            ):
                reserved[sid] += people
                pending.append((cert_id, sid, people, -1))
        return LedgerView(
            timestep=timestep,
            capacity_total={sid: c for sid, c, _ in rows},
            occupancy={sid: o for sid, _, o in rows},
            reserved=reserved,
            pending=tuple(pending),
            occupancy_sigma={sid: 0.0 for sid, _, _ in rows},
            occupancy_age_s={sid: 0.0 for sid, _, _ in rows},
        )

    @contextmanager
    def transaction(self) -> Iterator[_SqliteTx]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield _SqliteTx(self)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def certificates(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT cert_json FROM certificates ORDER BY seq").fetchall()
        return [json.loads(r[0]) for r in rows]

    def inputs(self, cert_id: str) -> CertificateInputs:
        with self._lock:
            row = self._conn.execute(
                "SELECT inputs_json FROM certificates WHERE cert_id=?", (cert_id,)
            ).fetchone()
        if row is None:
            raise KeyError(cert_id)
        return CertificateInputs.from_dict(json.loads(row[0]))

    def next_cert_id(self, prefix: str = "CERT") -> str:
        with self._lock:
            ids = [r[0] for r in self._conn.execute("SELECT cert_id FROM certificates")]
        return _next_id(ids, prefix)


class _SimTx:
    def __init__(self, adapter: "SimLedgerAdapter") -> None:
        self._a = adapter
        self.reserved: list[tuple[str, int, str]] = []
        self.released: list[tuple[str, int, str]] = []
        self.pending_cert: tuple[dict, CertificateInputs] | None = None

    def reserve(self, shelter_id: str, people: int, cert_id: str) -> None:
        self.reserved.append((shelter_id, people, cert_id))

    def release(self, shelter_id: str, people: int, cert_id: str) -> None:
        self.released.append((shelter_id, people, cert_id))

    def append_certificate(self, cert: Mapping, inputs: CertificateInputs) -> None:
        self.pending_cert = (dict(cert), inputs)


class SimLedgerAdapter:
    """Ledger over a v4 ``StochasticSimulator``; the transaction commit steps the simulator."""

    def __init__(self, simulator) -> None:
        self.simulator = simulator
        self._certs: list[dict] = []
        self._inputs: dict[str, CertificateInputs] = {}
        self.last_transition = None

    def view(self) -> LedgerView:
        state = self.simulator.prepared_state_for_debug()
        return ledger_view_from_state(state, self.simulator.transit_plans())

    def next_group_id(self) -> str:
        return f"dispatch-{self.simulator.prepared_state_for_debug().next_dispatch_sequence:06d}"

    @contextmanager
    def transaction(self) -> Iterator[_SimTx]:
        from src.sim import DispatchAction, WaitAction

        tx = _SimTx(self)
        yield tx  # an exception here discards everything; the simulator is not stepped
        if tx.pending_cert is None:
            raise LedgerConflict("transaction ended without a certificate")
        cert, inputs = tx.pending_cert
        key = cert["chosen"]["action_key"]
        if cert["kind"] == "MIGRATION":
            cand = next(c for c in inputs.candidates if c.action_key == key)
            try:
                self.simulator.migrate(cert["chosen"]["group_id"], cand.shelter_id, cand.edge_ids)
            except ValueError as exc:
                raise LedgerConflict(str(exc)) from exc
            self.last_transition = None
            self._certs.append(cert)
            self._inputs[cert["cert_id"]] = inputs
            return
        if key == "WAIT":
            action = WaitAction()
        else:
            zone, shelter = key.split("->", 1)
            action = DispatchAction(zone, shelter)
        transition = self.simulator.step(action)
        if not transition.accepted:
            raise LedgerConflict(f"simulator refused {key}")
        self.last_transition = transition
        self._certs.append(cert)
        self._inputs[cert["cert_id"]] = inputs

    def certificates(self) -> list[dict]:
        return list(self._certs)

    def inputs(self, cert_id: str) -> CertificateInputs:
        return self._inputs[cert_id]

    def next_cert_id(self, prefix: str = "CERT") -> str:
        return _next_id([c["cert_id"] for c in self._certs], prefix)
