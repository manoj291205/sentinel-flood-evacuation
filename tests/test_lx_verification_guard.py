"""Verify child-process offline and artifact isolation without touching real artifacts."""
import os
from pathlib import Path
import subprocess
import sys


def test_verification_guard_blocks_network_and_protected_writes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    protected = tmp_path / "protected"
    protected.mkdir()
    script = """
import socket
from pathlib import Path
import os
p = Path(os.environ['SENTINEL_PROTECT_WORKTREE']) / 'untouched.txt'
try:
    p.write_text('must not be written', encoding='utf-8')
except PermissionError:
    pass
else:
    raise AssertionError('protected write was allowed')
try:
    socket.getaddrinfo('example.invalid', 443)
except PermissionError:
    pass
else:
    raise AssertionError('external DNS was allowed')
print('offline isolation verified')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(root / "scripts/verification"),
                                 "SENTINEL_PROTECT_WORKTREE": str(protected)},
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "offline isolation verified"
    assert not list(protected.iterdir())
