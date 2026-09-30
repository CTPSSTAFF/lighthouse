# 64 GB laptop memory qualification plan

Status: implementation and validation in progress on branch `codex/laptop-memory-qualification`.

Acceptance amendment (user, 2026-09-29): no representative 64 GB laptop is available. Complete the
constrained-container tests here, targeting approximately 50–55 GB maximum model memory as a proxy.
Physical-laptop responsiveness and swap validation are deferred and are not a completion requirement
for this execution of the plan.

## Objective and budget

Run the complete current Lighthouse model on a laptop with 64 GB RAM while retaining usable memory
for the operating system and ordinary background applications. The earlier 52 GB figure was
approximate; avoiding OOM, sustained swap growth, and severe host memory pressure is the actual
requirement. Qualification is specific to the tested OS, architecture, backend, worker count,
inputs, dependencies, and configuration.

Use bytes for calculations and show both decimal GB and binary GiB in reports. Establish the budget
from measured physical RAM, rather than assuming that a machine advertised as 64 GB has exactly 64
GiB. Reserve at least 12 GiB for the host; aim for more headroom where practical.

For a 64 GiB host, use this initial container profile:

| Item | Initial budget | | --- | --- | | Host OS and background applications | At least 12 GiB | |
Entire Docker Linux VM | 52 GiB | | Container hard limit, including charged shared memory and file
cache | 50 GiB | | Container qualification peak | At most 48 GiB | | Container swap | Disabled | |
`/dev/shm` capacity | 16 GiB, charged within the container limit as used |

The VM budget leaves 2 GiB above the container limit. This is a starting allocation, not proof that
VM overhead will always fit. Reduce the model/VM budgets if the host has less physical RAM or
background usage requires more space. For native Linux, a 50 GiB qualification target and 52 GiB
hard limit may be appropriate on a 64 GiB host because there is no Docker Desktop VM; the measured
host reserve still governs. Do not count swap as additional RAM.

The development Mac has 128 GiB RAM. A constrained run here can establish the model/container
budget, but cannot by itself demonstrate host responsiveness or swapping on a 64 GB laptop. Final
end-to-end validation should use a representative 64 GB machine and intended runtime.

## Starting findings

The review baseline is Lighthouse `89faf63` on branch `ACTIONER`. Preserve unrelated work, including
the untracked `.github/github-app.yml`.

- Both benchmark workers clear `imported_extensions`, leaving six configured Lighthouse steps
  unregistered. The README CLI correctly requires `--ext extensions`.
- The full data currently contain 3,602,383 households, 8,674,446 persons, and 5,839 zones.
  `persons.parquet` lacks the required `naics_code`. Updated production persons data are being
  supplied by the user. Counts may legitimately change with that update and must be recorded.
- Destination chunk settings and the split tour/at-work worker phases remain. Trip-mode
  `explicit_chunk: 100_000` lives in `configs_explicit_chunk`, which neither benchmark loads. The
  installed ActivitySim 1.6 supports it.
- The monitor implementation has reverted to hardcoded phases while its documentation and tests
  expect the run-plan-based implementation from commit `68a8d12`.
- Production resume compares unequal specifications: the saved specification includes
  `allocator_environment`, while the expected specification omits it.
- The Dockerfile reruns dependency resolution and carries obsolete sibling-source build plumbing;
  the current project and lockfile select released packages.
- Production exit status currently indicates execution success, not qualification success. Missing
  memory readings can become zero, so measurement validity needs explicit validation.

## Phase 1: Repair execution and reproducibility

This phase does not require the updated full persons file.

1. Make both benchmark workers import the Lighthouse `extensions` module and pass its name to
   spawned workers. Follow the proven module-name approach in `scripts/model_ci.py`; ensure the
   model working directory is available in parent and child processes. Retain safe skim loading and
   verify that benchmark and extension guards coexist.
1. Define a documented laptop benchmark profile that includes `configs_explicit_chunk` ahead of the
   existing configuration directories. Apply it consistently in warm-up and measured jobs, and in
   both sides of any Sharrow/non-Sharrow comparison. Preserve the ordinary base configuration;
   provide an explicit way to test it without this profile.
1. Include every selected overlay, model extension, benchmark worker, lockfile, and relevant runtime
   setting in run provenance. Record seed, package versions, image ID, architecture,
   allocator/thread settings, checkpoint/output settings, and input identities/checksums.
1. Build the qualification image directly from the checked-in lock using locked installation. Remove
   unnecessary sibling checkout requirements and stale local-source image hashing. Do not silently
   resolve a new lock or substitute development packages. Record installed versions inside the built
   image.
1. Generate saved and expected run specifications from the same function. Include allocator, input
   identity, code/configuration, backend, and cache compatibility information. Reuse only compatible
   completed jobs; preserve incomplete jobs. Distinguish reusing a completed job from resuming a
   model checkpoint. New qualification measurements must execute fresh jobs.

Acceptance: focused tests cover extension registration in spawned workers, effective profile
settings, compatible reuse, and invalidation after input/configuration/code changes. A small
single-process and multiprocess run complete all configured steps with valid outputs. The image uses
the intended locked releases without requiring sibling repositories.

## Phase 2: Repair monitoring and qualification decisions

This phase can proceed using synthetic fixtures and existing test inputs.

1. Reconcile `sys_monitor.py` with the run-plan implementation introduced by `68a8d12`, retaining
   any subsequent useful changes. Restore dynamic phase/step/worker discovery, `--run-list`,
   complete log replay, resume handling, and failure/finalization states. Use the existing monitor
   fixtures rather than inventing another hardcoded step list.
1. Keep system-monitor memory explicitly labeled as whole-host memory. `--parent-pid` controls
   lifetime only; it does not make the samples process-specific. Treat its progress as a diagnostic
   and verify overall completion from the model's actual success records.
1. Validate cgroup v2, required memory files, actual memory/swap limits, and successful sampling
   before accepting a production result. Missing/unsupported/failed measurements must yield an
   unqualified result, never a zero-byte pass. Capture the final cumulative kernel peak before
   normal container teardown; preserve failure evidence after OOM or safety stops.
1. Make execution success and memory qualification separate explicit report fields. A requested
   qualification should return failure when no full-population candidate qualifies. Clearly label
   partial sweeps, smoke samples, warm-ups, and historical reused jobs; none establish a new
   full-population pass.
1. Require a qualifying candidate to complete successfully, stay within its configured peak, have
   valid measurements and no OOM events, and use no container swap. Keep host pressure aborts
   distinct from model/container OOM failures. Record available memory and host swap before, during,
   and after the run; examine growth rather than rejecting pre-existing swap.
1. Keep raw cgroup peak as the budget metric. Working-set estimates, summed process RSS/USS, and
   per-component overlap are diagnostic only. Expose peak timing, phase, and memory breakdown where
   available, without claiming overlapping components own all sampled memory.

Acceptance: existing monitor tests pass. Focused benchmark tests exercise missing readings,
over-target successful runs, OOM, safety stops, zero/nonzero swap, and valid passing results.
Synthetic container checks verify limit enforcement and reporting without a full simulation.

## Phase 3: Input preflight and integration validation

Implement preflight now; full-data validation waits for the user's updated persons file.

- Check required columns, person/household IDs and joins, eligible-worker industry coverage,
  supported industry values, household income, land-use references, and skim zone mappings. Reuse
  existing model/CI validation rules where possible. Avoid loading unnecessary full copies of large
  tables in the host-side validator; use metadata and bounded reads.
- Fail with actionable diagnostics before a long model run or expensive compilation. Do not
  manufacture production industry values, remove new components, or substitute subarea data to get a
  memory pass. Keep user-supplied source data unchanged.
- While waiting, use existing valid `model/data` and frozen fixtures to validate the repaired
  harness and profile. These runs establish functionality only. Test the full-data preflight against
  the current missing-column case and report it as an expected prerequisite failure.
- Run the repository's focused tests and the existing 2,000-household backend comparison. Compare
  profile-on/profile-off decoded outputs with the same seed and workers to detect chunking
  regressions. Preserve existing exact-choice and logsum-tolerance contracts.

Acceptance: both backends and extensions run correctly on the fixture, the profile does not
introduce unapproved behavioral changes, and preflight reports precisely what the full data lack.

## Phase 4: Full-scale qualification after input delivery

1. Record the supplied input checksums and rerun preflight. Start Docker and check actual VM RAM,
   cgroup support, free disk, and host baseline. Ensure no competing model job is running.
1. Run a 5,000-household integration sample against the full land-use and skim inputs. Exercise the
   entire model, coalescing, matrices, and final output writing. A population sample does not
   predict full-population peak memory and is not a qualification pass.
1. Execute the full population with seed fixed and worker counts 2 and 4, in separate fresh output
   directories under the declared laptop profile. Let the harness warm the compiled cache, but
   monitor warm-up as well. Preserve all production steps and shadow-pricing settings. Record
   resolved worker counts for every phase rather than assuming every phase uses N.
1. Inspect raw peaks, host pressure, runtime, and output validity. Do not automatically continue to
   larger worker counts after a failure. A lower worker count is not guaranteed to use less memory
   because its individual shards are larger.
1. If neither candidate qualifies, locate the peak phase and memory type. Change one relevant
   chunk/worker/phase/cache setting at a time, validate numerical behavior, and rerun. Do not raise
   the laptop budget or suppress model work to make a pass. Diagnose shared-memory capacity errors
   separately from total-memory exhaustion.
1. Repeat the selected configuration in a fresh output directory. Include both a cold-cache
   startup/warm-up lifecycle and a warm-cache repeat; the complete lifecycle must fit, not only
   steady-state simulation. Choose the fastest configuration with repeatable headroom.
1. Run the selected profile on the representative 64 GB laptop. Measure whole-host headroom, swap
   growth, memory pressure, and ordinary interactive responsiveness. If that hardware is
   unavailable, report only container-budget qualification and leave laptop validation pending.

Planned initial full-scale command, after the harness repairs and input update (the laptop overlay
must be enabled by the repaired runner):

```sh
cd /Users/jpn/Git/boston-model/lighthouse
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full \
  --sample-households 0 \
  --processes 2 4 \
  --memory-limit 50g \
  --qualification-peak 48g \
  --shm-size 16g \
  --sample-interval 1 \
  --cache-dir model/output/laptop-qualification-cache \
  --output-dir model/output/laptop-qualification/timestamp
```

These `g` values use binary GiB. Do not run this command against the unrepaired harness or the
current incomplete full persons input. Smoke runs use a separate output directory and
`--sample-households 5000`; cold-cache tests use a new cache directory.

## Phase 5: Documentation and handoff

- Update README, monitoring, and execution-backend documentation with tested commands, correct
  extension working directories, the laptop profile, GB/GiB units, and input prerequisites.
- Explain which benchmark to use: production for memory qualification, performance for backend
  comparison, system monitor for host context and progress. Document resume/cache behavior.
- Deliver `report.html`, `metrics.json`, raw cgroup and host samples, effective configuration,
  input/code/environment provenance, completion evidence, and output validation summaries. Keep
  private inputs and large generated outputs out of version control.
- State the qualified worker count, peak, runtime, host reserve, cache state, and tested platform.
  Explicitly record unresolved limitations or a failed qualification; do not infer success from a
  small sample, process exit code, or earlier model version.

## Work sequencing and completion gates

Implement phases 1–3 and their documentation while production inputs are pending. No dependency on
the new persons file should delay harness repairs, monitor tests, container measurement tests, or
fixture integration runs. Phase 4 is the only phase requiring the updated full population.

The work is complete when the repaired tools and tests pass, reproducible full-population runs meet
the model memory budget with valid outputs, and a representative 64 GB host demonstrates adequate
headroom without sustained swap growth or severe memory pressure. Until that final host check, label
the result as a measured container budget rather than a laptop guarantee.
