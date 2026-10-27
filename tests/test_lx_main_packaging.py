"""Exercise metadata against the files declared for the Docker runtime stage."""
from __future__ import annotations

import importlib
from pathlib import Path
import shlex
import shutil

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_inputs_preserve_project_and_research_metadata(tmp_path, monkeypatch):
    facts = importlib.import_module("src.api.project_facts")
    library = importlib.import_module("src.api.library")
    facts.project_facts.cache_clear()
    library.library_index.cache_clear()
    library.library_v3.cache_clear()
    expected_facts = facts.project_facts()
    expected_v3 = library.library_v3()

    runtime = False
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        parts = shlex.split(line)
        if not parts:
            continue
        if parts[0] == "FROM":
            runtime = parts[1].startswith("python:")
        if not runtime or parts[0] != "COPY" or parts[1].startswith("--"):
            continue
        destination = tmp_path / parts[-1]
        assert destination.resolve().is_relative_to(tmp_path.resolve())
        for source in parts[1:-1]:
            original = ROOT / source
            if original.is_dir():
                shutil.copytree(original, destination, dirs_exist_ok=True)
            else:
                target = destination / original.name if parts[-1].endswith("/") else destination
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)

    monkeypatch.setattr(facts, "ROOT", tmp_path)
    monkeypatch.setattr(library, "ROOT", tmp_path)
    monkeypatch.setattr(library, "P27", tmp_path / "data/eval_results/phase27")
    facts.project_facts.cache_clear()
    library.library_index.cache_clear()
    library.library_v3.cache_clear()
    try:
        assert facts.project_facts() == expected_facts
        assert library.library_v3() == expected_v3
    finally:
        facts.project_facts.cache_clear()
        library.library_index.cache_clear()
        library.library_v3.cache_clear()
