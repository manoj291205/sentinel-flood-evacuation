"""Opt-in offline verification guard; activate with PYTHONPATH=scripts/verification.

Allows loopback for local browser/API tests. Refuses external network access and
writes to frozen artifacts, including child Python processes that inherit PYTHONPATH.
Package installation must run without this guard.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PROTECTED = [ROOT / path for path in (
    "data/eval_v3", "data/eval_results", "data/eval_v4", "models",
    "data/geospatial_v3", "data/geospatial_v4", "data/demo_v4",
)]
if os.getenv("SENTINEL_PROTECT_WORKTREE"):
    PROTECTED.append(Path(os.environ["SENTINEL_PROTECT_WORKTREE"]).resolve())

for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(name, None)
os.environ.update(HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", ANONYMIZED_TELEMETRY="False")


def _protected(path):
    if not isinstance(path, (str, bytes, os.PathLike)):
        return False
    candidate = Path(os.fsdecode(path)).resolve()
    return any(candidate == root or root in candidate.parents for root in PROTECTED)


def _audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        address = args[0] if event == "socket.getaddrinfo" else args[-1]
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="replace")
        if host not in {"localhost", "127.0.0.1", "::1", None}:
            # Unix-domain sockets are local and have no IP port tuple.
            if isinstance(address, tuple) or event == "socket.getaddrinfo":
                raise PermissionError("External network blocked during offline verification")
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and _protected(path):
            raise PermissionError("Protected artifact write blocked during verification")
    if event in {"os.remove", "os.rmdir", "os.mkdir", "os.rename"}:
        paths = args[:2] if event == "os.rename" else args[:1]
        if any(_protected(path) for path in paths):
            raise PermissionError("Protected artifact mutation blocked during verification")


sys.addaudithook(_audit)
