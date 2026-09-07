# Sentinel-Agent V3 Baseline

This file freezes the measured V1/V2 repository state from which V3 begins. It records
existing results; it does not reinterpret them or introduce V3 simulator results.

## Snapshot

| Item | Baseline |
| --- | --- |
| Capture date | 2026-09-06 (Asia/Kolkata) |
| V3 branch | `v3-dynamic-stochastic` |
| Baseline commit | `d998aac367b20fe0e9f557beee509b71957558d0` |
| Parent branch | `v2-resources` at the same commit |
| `main` at capture | `72bfaea0059dbab12b434b0fcf30849b51c2dfb0` |
| Frozen V1 tag | `v1-capstone-demo` → `f19cccc6e82efa99f921ad601ea7101b81068b41` |
| Tracked files | 60 |
| Python | 3.11.3 (`.venv/bin/python`) |

V3 intentionally branches from `v2-resources`, not the older `main`, because the v2
branch contains the Gate 1A and Gate 1A.5 negative results that motivate V3's stochastic
formulation. No history, tag, or historical result was rewritten.

## Dependency pins

`requirements.txt` SHA-256:
`822fc26a7814f7d4e9bc38e213a806399fb7157a9e7bef7f439a09f605dcee71`.

| Package | Pin |
| --- | --- |
| `pypdf` | 6.16.2 |
| `sentence-transformers` | 6.0.1 |
| `chromadb` | 1.5.9 |
| `google-genai` | 2.21.0 |
| `gymnasium` | 1.3.0 |
| `stable-baselines3` | 2.9.0 |
| `sb3-contrib` | 2.9.0 |
| `streamlit` | 1.63.0 |
| `pytest` | 9.1.1 |

These are the project's direct, fully pinned dependencies. The repository does not yet
carry a transitive lockfile; reproducibility therefore depends on the pins above plus the
captured Python version.

## Existing test and model baseline

| Check | Result |
| --- | --- |
| Offline invariant suite | **43 passed in 0.31 s** |
| Command | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/` |
| V1 checkpoint | `models/maskable_ppo_shelter.zip` (180 KiB) |
| Checkpoint SHA-256 | `24755decaa400533103a4e4386c908c4ae70715d4fce4aca1379c272bde99702` |
| Load check | **Passed** as `MaskablePPO`, CPU |
| Observation space | `Box(0.0, inf, (28,), float32)` |
| Action space | `Discrete(7)` |

## Held-out decision baseline

Source: `data/eval_results/ablation_study.json`, 60 synthetic held-out scenarios,
suite seed `20260902`. Artifact SHA-256:
`058e0c5edae214b5e005c44d35c6b12b3342dde240fad67ea21a138bcadd9565`.

| Measure | Baseline result |
| --- | ---: |
| Current RL policy, constrained, held-out optimal rate | **73.33%** (44/60) |
| Greedy reward oracle, constrained, held-out optimal rate | **93.33%** (56/60) |
| Unsafe picks with constraints | **6.67%** (4/60) |
| Unsafe picks without constraints | **40.00%** (24/60) |
| Scenarios where constraints changed the policy choice | **40.00%** (24/60) |

The four constrained unsafe picks are the suite's `no_safe_shelter` cases. These figures
measure the V1 architecture using the deterministic safety rule, not Gemini accuracy.
The existing negative result remains unchanged: greedy is the oracle for this one-step
reward and outperforms the V1 policy.

## RAG and evidence baseline

| Item | Baseline |
| --- | --- |
| Distinct authoritative documents | **1** |
| Source | NDMA, *National Disaster Management Guidelines: Management of Floods* |
| Source pages | 168 |
| Source bytes | 6,120,219 |
| Source SHA-256 | `2fc4518a29c249c91d223eb6edb6f5cba23d3fa85eaaa8a71d319bdde451981f` |
| Mirror handling | NIDM URL recorded as a byte-identical mirror, not a second document |
| Local Chroma collection | `flood_guidelines` |
| Indexed page-scoped chunks | **480** |
| Dense embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Cached Gemini model id | `gemini-3.6-flash` |
| Cached demo citations | **7/7 verified verbatim** |

The cached constraint artifact SHA-256 is
`dd78b957b56bd064de7f7997093df197b505f6798107c5802c58437ce8bb4a37`.
The document is real; the scenario is fictional; verdicts are model-generated; the
rates above are experimentally measured.

## Demo baseline

Offline command:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_demo.py
```

Result: **exit 0**.

```text
RECOMMENDED SHELTER : S5
  flood severity 0.05 (minimal)
  1,010 spare places for 700 evacuees, 41 min away
  policy score 0.6500, regret 0.0742

with the RAG-grounded constraints : S5 (severity 0.05, score 0.6500)
with NO constraints at all        : S1 (severity 0.85, score 1.0000)
```

The run loaded the committed PDF, existing 480-chunk index, cached Gemini constraints,
and committed checkpoint. It made no API call and performed a live local retrieval.

Without the explicit Hugging Face offline flags, the same run still exits 0 but the
embedding loader attempts several metadata `HEAD` requests before falling back to its
local cache. This is a reproducibility/latency limitation in the current offline path,
not a result failure.

## Dashboard smoke test

Status: **Passed at server and app-execution level**.

- Streamlit bound to `127.0.0.1:8765` in headless mode.
- `/_stcore/health` returned `ok`.
- The initial HTML endpoint returned successfully.
- `streamlit.testing.v1.AppTest` executed `src/dashboard/app.py` with zero exceptions and
  one page title.

This Phase 0 check did not repeat the historical pixel-level browser/accessibility audit;
it verifies that the current dashboard starts and executes against the frozen artifacts.

## Artifact integrity

No V1 scenario, model, source PDF, cached constraint, evaluation JSON, or measured result
was modified during Phase 0. The V1 tag remains resolvable, and the V3 branch adds only
baseline/documentation files before later implementation begins.

## Phase 0 acceptance criteria

- [x] Existing tests pass.
- [x] Current demo exits 0 in explicit offline mode.
- [x] Current model artifact loads.
- [x] Baseline metrics are recorded from the committed evaluation artifact.
- [x] `v1-capstone-demo` exists and resolves.
- [x] Current documentation inventory matches the repository's functional areas.
- [x] `v3-dynamic-stochastic` exists and is checked out.
- [x] No V1 result changed.

## Known limitations

- Direct dependencies are pinned, but there is no transitive lockfile.
- Normal demo execution attempts Hugging Face metadata requests unless offline environment
  variables are set, although it ultimately uses the local model cache and succeeds.
- The dashboard smoke test is not a replacement for the earlier full browser visual audit.
- The V1 policy remains inferior to its closed-form greedy oracle; V3 must not claim
  otherwise.

