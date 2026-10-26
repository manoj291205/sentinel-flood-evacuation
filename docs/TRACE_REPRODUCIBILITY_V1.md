# Trace reconstruction and portability contract v1

This is a separate diagnostic contract. It does not replace, relax or rename
`test_trace_rebuilds_byte_identically_and_validates`. The original strict test and
`data/demo_v4/demo_trace.json` remain unchanged.

## Forensic result

The unchanged default numerical implementation still differs from the stored trace
in exactly five binary64 values. All occur in `inputs/CERT-000007/forecast` at step 5:

| Field | Reconstructed hexadecimal float | Stored hexadecimal float |
|---|---|---|
| zone_severity/Z2 | `0x1.551cd149df6e4p-1` | `0x1.551cd149df6e5p-1` |
| shelter_severity/S1 | `0x1.13c182d039d60p-1` | `0x1.13c182d039d61p-1` |
| shelter_severity/S2 | `0x1.51846e5936a2cp-1` | `0x1.51846e5936a2dp-1` |
| shelter_severity/S4 | `0x1.14110627ba7fbp-1` | `0x1.14110627ba7fcp-1` |
| shelter_severity/S5 | `0x1.41da205e17b4bp-1` | `0x1.41da205e17b4cp-1` |

Each is one ULP. The integer scenario seed is 3656791691536331930, derived from
generator seed 620003. Scenario generation, keyed SHA-256 payloads, RNG namespaces,
hazard equations and operation ordering are unchanged from starting main. Default
main and the corrected branch produce the same five discrepancies. The differences
already exist before JSON serialization, and JSON round-trips preserve the binary
values. NumPy is not the RNG used on this call path.

The causal path is `EpisodeRandomStreams.normal` → Box–Muller `math.cos` → regional
AR(1) hazard update → observable forecast → raw stored certificate inputs. At the
regional draw for timestep 3, the binary64 angle is `0x1.e44d077d985b7p-1`:

- Native cosine on this Mac: `0x1.2b86d4616a392p-1`.
- Independent 100- and 180-digit reference cosine: `0x1.2b86d4616a393p-1`.

A process-only diagnostic replacing the cosine calculation for that single regional
draw with the independent reference makes the ENTIRE reconstructed trace exactly
equal to the frozen JSON, with zero differing fields. Replacing all episode-stream
cosines with the reference also reproduces it exactly. This is causal diagnostic
evidence, not a production patch or proof that the original producer used this
reference implementation. Other tiny coefficient changes can also affect rounding;
they are not legitimate fixes and were not applied.

Native Python 3.11.3, isolated Python 3.12.15 and available Python 3.13.5 return the
same native cosine here. The full reconstruction was checked on 3.11/NumPy 2.4.6
and 3.12/NumPy 2.5.4 with SciPy 1.18.1 in the latter environment. The original trace
was introduced at d99ea4d, whose `.python-version` says 3.11. The later runtime
requirements are not an exact producer lock: the original C library/build/platform
identity is not recorded. The original environment therefore cannot be fully asserted.

Classification: **B, numerical environment compatibility, supported by isolated
cosine reproduction; D, missing historical producer details, still applies.** There
is no evidence of an integration algorithm regression (A), and the mismatch is not
created by JSON serialization (C). CPython documents that its math functions mostly
wrap the platform C math library: https://docs.python.org/3.12/library/math.html.

## Separate diagnostic acceptance

Contract ID: `sentinel-trace-portability-v1`.

1. Preserve and report raw byte/value equality independently as `strict_equal`.
2. Require exact equality of configuration, graph, decisions, certificates and their
   hashes, route ordering, ledger, timing, counts and every non-exempt trace field.
3. For only raw zone/shelter severity arrays in forecast inputs, permit a separate
   **hash-equivalent** result only if the existing registered `forecast_hash()` is
   identical. That existing contract canonicalizes floats at nine decimal places;
   no new arbitrary epsilon or ULP tolerance is introduced.
4. Report every raw difference. A hash-equivalent result must not be called strict
   reconstruction success, exact state equality, a passing original test, or validation
   of unseen trajectories. It grants no operational authorization or citation permission.
5. Certificate v2 input digests remain exact. This diagnostic cannot relax them.

Tests reject altered actions, certificate hashes, route ordering, configuration and
hazards that change the registered forecast hash. This is a bounded portability
diagnostic for the recorded six-step demo, not a new scientific evaluation result.

## Read-only reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/scripts/verification:$PWD" \
  .venv/bin/python scripts/trace_forensics.py --reference-cos
```

The script writes only its stdout. The reference profile is process-local and restored
in `finally`; production RNG source/configuration remains unchanged. The reference uses
standard-library Decimal Taylor evaluation, cross-checked with independent high-precision
arithmetic. It is a diagnostic, not a new runtime dependency or deployed RNG backend.

Default output: `strict_equal=false`, `hash_equivalent=true`, five raw paths.
Reference diagnostic output: `strict_equal=true`, zero raw paths on this environment.
The script's exit status indicates diagnostic completion, not strict-test success.

The original, unmodified strict pytest case was also run under the explicit process-only
reference override and passed (1 passed in 12.35 seconds). Under the production default it
still fails. This controlled comparison changes no assertion or frozen byte and does not
make the default-runtime release requirement green.

Release position: the original strict requirement remains unmet by the default runtime.
Establish the original producer environment or obtain explicit review approval for a
future numerical profile before claiming cross-environment byte identity. Do not mutate
frozen artifacts, fit coefficients, special-case timestep 3 or insert a tolerance.
