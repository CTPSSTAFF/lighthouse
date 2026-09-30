# Laptop memory qualification results

Status: **all five phases complete, 2026-09-30**. Full-population two-worker and four-worker runs
qualify, including the selected four-worker fresh repeat. Physical 64 GB hardware validation is
deferred under the agreed proxy acceptance.

## Measured result

The complete four-worker model qualified twice. The worst kernel-recorded peak was
**50,228,416,512 bytes (50.23 GB / 46.78 GiB)**, below the 50,465,865,728-byte qualification
target (47 GiB) and 52,076,478,464-byte hard cap (48.5 GiB). Both runs completed every model,
trip matrices, final tables, and output validation. There were no OOM events, container swap,
safety stops, or host swap growth.

| Run | Cache lifecycle | Peak GB | Peak GiB | Duration including validation | Result |
| --- | --- | ---: | ---: | --- | --- |
| Single-process 5,000-household warm-up | New empty cache | 24.50 | 22.82 | 343.95 s | Valid warm-up |
| Full population, 4 workers | Fresh output after cold warm-up | 47.50 | 44.24 | 8,257.99 s (2 h 17 m 38 s) | Qualifies |
| Full population, 2 workers | Fresh output, warm compiled cache | 47.43 | 44.17 | 11,964.09 s (3 h 19 m 24 s) | Qualifies |
| Full population, 4-worker repeat | Fresh output, warm compiled cache | 50.23 | 46.78 | 8,253.52 s (2 h 17 m 34 s) | Qualifies |

**Use four workers with the tested laptop profile and explicit limits below.** Both four-worker runs
completed about 31% faster than two. The repeat's brief peak during the nonmandatory scheduling/tour
mode transition was higher than the first run: worker timing and allocation overlap affect the
maximum. Its margin was **0.24 GB below the qualification target and 1.85 GB below the hard cap**.
This meets the requested roughly 50–55 GB proxy, but the target margin is small; the result does not
justify increasing workers or memory-heavy settings without another qualification run.

The two four-worker runs have identical input/code hashes and run settings, apart from output
paths. Their final accessibility, land-use, household, person, tour, and trip Parquet files are
**byte-identical**. The compilation cache started empty for the first lifecycle and was reused for
the repeat; this does not claim a cold operating-system disk cache. All monitored warm-ups passed,
with peaks of 24.50–24.52 GB. Full-run timings in the table exclude that separate warm-up;
allow about six additional minutes for the tested cold compilation lifecycle and about two for
a warm-cache lifecycle.

The four-worker output validation confirmed 3,602,383 households, 8,674,446 persons, 12,067,303
tours, and 30,730,651 trips. The two-worker run had the same household, person, and tour counts
and 30,725,095 trips; qualification is worker-configuration-specific. Checks cover population counts, unique IDs, household/person/tour
ownership, zones, modes, tour times, departure bounds, and tour coverage. Fixture comparisons
separately enforce exact choices and the existing logsum tolerance; forced small bounded joins
matched all fixture values exactly, including logsums. The unit/integration suite passed 148 tests.
The final fresh 2,000-household laptop-profile Sharrow/non-Sharrow comparison also passed: every
non-logsum output matched exactly, with a maximum logsum absolute difference of 0.00000501
under the unchanged `rtol=atol=1e-5` contract. Both fixtures completed all steps and output validation.

## Repairs and validation

| Phase | Delivered work | Evidence |
| --- | --- | --- |
| 1. Execution and reproducibility | Spawn-safe extension imports, consistent laptop overlay, locked image, complete provenance and compatible reuse | Both benchmark scripts completed sampled jobs; image uses released locked packages |
| 2. Monitoring and decisions | Run-plan progress, strict cgroup measurements, explicit qualification, OOM/swap/host-pressure handling | Monitor fixtures, benchmark decision tests, and synthetic limit/OOM containers |
| 3. Inputs and integration | Revised full-data preflight; exact-choice and logsum comparisons | Full population and seven OMX inputs validated; 148 tests passed; bounded-join fixtures preserve random streams |
| 4. Full-scale qualification | Fixed chunk targets and bounded joins; fresh two- and four-worker full runs | Both candidates and the selected four-worker fresh repeat qualify; repeated final tables are byte-identical |
| 5. Handoff | Tested commands, limits, provenance, raw evidence, and platform limitations | Complete: tested commands and evidence retained; final backend comparison passed; Docker allocation restored |

Full-scale failures identified allocations outside ActivitySim's internal utility chunking:
wide person-to-alternative logsum joins, population-dependent destination sample chunks,
and wide tour/person joins before stop and trip models. The laptop profile now bounds those
joins, selects only required attributes, and releases recomputable cached joins. It preserves
all model steps, shadow-pricing settings, destination alternatives, matrices, and final outputs.
The ordinary base profile remains available. Compatibility overrides are tied to the locked
ActivitySim interfaces and should be revalidated when dependencies or chooser specifications change.

## Tested platform and budget

- macOS 26.6.2, ARM64, 128 GiB physical memory; Docker Engine 29.8.1 on Docker Desktop, Linux aarch64, cgroup v2.
- Docker VM configured to 52 GiB; Linux reported 54,643,150,848 bytes (50.89 GiB) usable memory.
- Container hard cap 48.5 GiB, qualification target 47 GiB, shared-memory capacity 16 GiB;
  shared pages and charged file cache are included in the cap and peak.
- Locked ActivitySim 1.6.0, Sharrow 2.16.2, NumPy 2.2.6, pandas 2.3.3; seed 0, laptop profile.
- Model/configuration fingerprint: `7bd8e63fb64bbfba666b48320e8456d12161c10095fc2fc7c6ad48fe32d592bd`.
- Image: `sha256:dee56b6b7123b091ef28cef011592fc38b6fced861ceba78e4e3d7c2bb990df2`.
- Tested model implementation: commit `2abb9bf` on `codex/laptop-memory-qualification`.

The development host retained at least 66.80 GB available during the first four-worker run and
61.54 GB during its repeat. That is context for this 128 GiB host, not proof of responsiveness on a physical 64 GB laptop. No such
machine is available; the user accepted constrained-container qualification as the current proxy.
The physical-laptop check remains a separate future test. Size its VM from actual physical bytes
and reserve memory for the OS and background applications. Do not add shared RSS across workers;
the model logs' summed RSS counts shared skims repeatedly and is not the authoritative peak.

The temporary Docker VM allocation was restored after qualification to its original 90,112 MiB
(88 GiB); the restarted VM and saved setting were verified.

## Evidence

Generated artifacts are local and ignored by Git; private inputs and large outputs are not committed.
Paths below are relative to the repository:

- Four-worker cold lifecycle: `model/output/laptop-final-cold/20260929-232758-213062/`.
- Two-worker comparison: `model/output/laptop-final-two/20260930-015230-745000/`.
- Four-worker repeat: `model/output/laptop-final-repeat/20260930-051418-256990/`.
- Full-output reproducibility: `model/output/laptop-repeat-validation.json`.
- Consolidated acceptance checks: `model/output/laptop-qualification-summary.json`.
- Test-suite and synthetic cgroup/OOM evidence: `model/output/laptop-final-validation/`.
- Final native backend fixtures: `model/output_laptop_ci_final_off/report/` and
  `model/output_laptop_ci_final_sh/report/`, including `backend-comparison.json`.
- Each lifecycle contains `report.html`, `metrics.json`, preflight, input checksums, and code hashes.
- Each job contains raw `cgroup-samples.csv` and `host-samples.csv`, `final-cgroup.json`,
  `run-result.json`, `output-validation.json`, effective settings, environment versions, and logs.
- Detailed failed-run and checkpoint-diagnostic history: `model/output/laptop-qualification-journal.md`.
  Resumed diagnostics and sampled smoke tests are not qualification passes.

## Reproduce the selected run

Configure the Docker VM from the available host budget, then run from the repository root:

```sh
uv sync --locked
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --profile laptop \
  --sample-households 0 --processes 4 \
  --memory-limit 48.5g --qualification-peak 47g --shm-size 16g \
  --sample-interval 1 \
  --cache-dir model/output/laptop-selected-cache \
  --output-dir model/output/laptop-selected/timestamp
```

A new cache directory provides a cold compilation lifecycle. Run the same command again with the
same cache and a fresh timestamped output for a warm repeat. A first invocation builds the locked
image; `--no-build` is appropriate only when intentionally reusing a verified matching image.
The [run guide](laptop-memory.md) explains measurement, smoke runs, resume behavior, and memory fixes.
