"""Durable issuance evidence for future provider runs; historical ledgers are never migrated.

A lost response or uncommitted successful response requires manual reconciliation.
It is never silently sent again. Known HTTP failures remain available for an explicit
later invocation, and all prior attempts stay in this journal.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


class ReconciliationRequired(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _atomic(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ProviderJournal:
    def __init__(self, path: Path, identity: dict, dispositions: list[dict], *, request_budget: int | None = None,
                 lock_path: Path | None = None):
        self.path, self.identity = Path(path), identity
        self.dispositions = dispositions
        self.request_budget = request_budget
        self.lock_path = Path(lock_path) if lock_path is not None else Path(str(self.path) + ".lock")
        self._lock = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self._lock).st_size == 0:
                    os.write(self._lock, b"0")
                os.lseek(self._lock, 0, os.SEEK_SET)
                msvcrt.locking(self._lock, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            expected = {row["claim_pair_id"]: _digest(row) for row in self.dispositions}
            if self.path.exists():
                try:
                    def unique(pairs):
                        value = {}
                        for key, item in pairs:
                            if key in value:
                                raise ValueError("duplicate provider journal key")
                            value[key] = item
                        return value
                    self.data = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                except (ValueError, OSError) as exc:
                    raise ReconciliationRequired("provider journal is unreadable; manual reconciliation required") from exc
                if not isinstance(self.data, dict) or set(self.data) != {"version", "identity", "committed", "requests", "batch"}:
                    raise ReconciliationRequired("provider journal structure changed")
                if self.data.get("version") != 1 or self.data.get("identity") != self.identity:
                    raise ReconciliationRequired("provider journal identity changed")
                if self.data.get("committed") != expected:
                    raise ReconciliationRequired("disposition changed or commit reconciliation required")
                requests = self.data.get("requests")
                if not isinstance(requests, list):
                    raise ReconciliationRequired("provider journal requests are malformed")
                attempts = {}
                for index, record in enumerate(requests):
                    if not isinstance(record, dict):
                        raise ReconciliationRequired("provider journal request is malformed")
                    pair_id = record.get("claim_pair_id")
                    if not isinstance(pair_id, str) or not pair_id:
                        raise ReconciliationRequired("provider journal item is malformed")
                    attempts[pair_id] = attempts.get(pair_id, 0) + 1
                    if type(record.get("attempt")) is not int or record["attempt"] != attempts[pair_id]:
                        raise ReconciliationRequired("provider journal attempt sequence changed")
                    fingerprint = record.get("request_sha256")
                    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(
                            letter not in "0123456789abcdef" for letter in fingerprint):
                        raise ReconciliationRequired("provider journal request fingerprint is malformed")
                    state = record.get("state")
                    if state in {"ISSUING", "AMBIGUOUS"}:
                        raise ReconciliationRequired("ambiguous provider request; never retry automatically")
                    if state not in {"INTENT", "RESOLVED"}:
                        raise ReconciliationRequired("provider lifecycle is malformed")
                    if state == "INTENT" and index != len(requests) - 1:
                        raise ReconciliationRequired("unfinished provider intent is not last")
                    for key in ("intent_utc",) if state == "INTENT" else ("intent_utc", "issued_utc", "resolved_utc"):
                        try:
                            stamp = datetime.fromisoformat(record[key])
                            if stamp.tzinfo is None:
                                raise ValueError("timezone missing")
                        except (KeyError, TypeError, ValueError) as exc:
                            raise ReconciliationRequired("provider journal timestamp is malformed") from exc
                    if state == "RESOLVED" and (type(record.get("http_status")) is not int
                                                or not 100 <= record["http_status"] <= 599):
                        raise ReconciliationRequired("provider journal response status is malformed")
                    if (state == "RESOLVED" and record.get("http_status") == 200
                            and record["claim_pair_id"] not in expected):
                        raise ReconciliationRequired("response is durable but disposition commit requires reconciliation")
            else:
                # Old incomplete logs cannot establish whether a missing attempt reached the provider.
                for old in (self.path.parent / "calls.jsonl", self.path.parent / "dispositions.jsonl"):
                    if old.exists() and old.stat().st_size:
                        raise ReconciliationRequired("historical provider logs have no issuance journal; manual reconciliation required")
                self.data = {"version": 1, "identity": self.identity, "committed": expected, "requests": [], "batch": None}
                _atomic(self.path, self.data)
            batch = self.data["batch"]
            if batch is not None and not isinstance(batch, dict):
                raise ReconciliationRequired("provider batch metadata is malformed")
            if batch is not None:
                if (set(batch) != {"state", "request_budget", "start_index"}
                        or batch["state"] not in {"RUNNING", "PAUSED"}
                        or type(batch["start_index"]) is not int
                        or not 0 <= batch["start_index"] <= len(self.data["requests"])
                        or (batch["request_budget"] is not None and (
                            type(batch["request_budget"]) is not int or batch["request_budget"] < 1))):
                    raise ReconciliationRequired("provider batch metadata is malformed")
                consumed = sum(record["state"] != "INTENT"
                               for record in self.data["requests"][batch["start_index"]:])
                if batch["request_budget"] is not None and consumed > batch["request_budget"]:
                    raise ReconciliationRequired("provider batch request budget was exceeded")
            if batch and batch.get("state") == "RUNNING":
                if batch.get("request_budget") != self.request_budget:
                    raise ReconciliationRequired("interrupted provider batch budget changed")
            else:
                if self.request_budget is not None and (type(self.request_budget) is not int or self.request_budget < 1):
                    raise ValueError("request budget must be a positive integer")
                self.data["batch"] = {"state": "RUNNING", "request_budget": self.request_budget,
                                      "start_index": len(self.data["requests"])}
                _atomic(self.path, self.data)
            return self
        except BaseException:
            os.close(self._lock)
            self._lock = None
            raise

    def __exit__(self, *_args):
        try:
            if _args[0] is None:
                self.data["batch"]["state"] = "PAUSED"
                _atomic(self.path, self.data)
        finally:
            if self._lock is not None:
                os.close(self._lock)
                self._lock = None

    def begin(self, pair_id: str, request: dict) -> int:
        if pair_id in self.data["committed"]:
            raise ReconciliationRequired("provider cannot rerun an already committed item")
        request_hash = _digest(request)
        requests = self.data["requests"]
        batch = self.data["batch"]
        used = sum(row["state"] != "INTENT" for row in requests[batch["start_index"]:])
        if self.request_budget is not None and used >= self.request_budget:
            raise ReconciliationRequired("provider request budget exhausted before issuance")
        if requests and requests[-1]["state"] == "INTENT":
            record = requests[-1]
            if (record["claim_pair_id"], record["request_sha256"]) != (pair_id, request_hash):
                raise ReconciliationRequired("unissued intent does not match this request")
        else:
            record = {"claim_pair_id": pair_id, "request_sha256": request_hash,
                      "state": "INTENT", "intent_utc": datetime.now(timezone.utc).isoformat(),
                      "attempt": sum(r["claim_pair_id"] == pair_id for r in requests) + 1}
            requests.append(record)
            _atomic(self.path, self.data)
        record.update(state="ISSUING", issued_utc=datetime.now(timezone.utc).isoformat())
        _atomic(self.path, self.data)
        return len(requests) - 1

    def resolve(self, index: int, response, failure) -> None:
        record = self.data["requests"][index]
        status = response.status if response is not None else getattr(failure, "status", None)
        ambiguous = response is None and (status is None or getattr(failure, "reason", None) == "NETWORK_ERROR")
        record.update(state="AMBIGUOUS" if ambiguous else "RESOLVED", http_status=status,
                      resolved_utc=datetime.now(timezone.utc).isoformat())
        if response is not None:
            # Hash malformed non-finite provider data without putting it into durable JSON values.
            decoded = json.dumps(response.body, sort_keys=True, separators=(",", ":"), allow_nan=True)
            record["response_sha256"] = hashlib.sha256(decoded.encode("utf-8")).hexdigest()
            try:
                content = json.loads(response.body["choices"][0]["message"]["content"])
                allowed = {"verdict", "confidence", "reason", "supporting_spans", "supporting_sentence_ids"}
                if isinstance(content, dict) and set(content) <= allowed:
                    _digest(content)  # Non-finite content is left to the frozen parser's retry policy.
                    record["normalized_content"] = content
            except (KeyError, TypeError, ValueError, IndexError):
                pass
        elif failure is not None:
            record["failure_type"] = type(failure).__name__  # Never exception text or headers.
        _atomic(self.path, self.data)

    def commit(self, row: dict) -> None:
        self.data["committed"][row["claim_pair_id"]] = _digest(row)
        _atomic(self.path, self.data)
