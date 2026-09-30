# Laptop memory qualification

The target is a complete model run on a 64 GB laptop with room for its operating system and
background applications. See the [implementation plan](laptop-memory-qualification-plan.md). Use
actual physical bytes when budgeting: 1 GiB is 1,073,741,824 bytes; 1 GB is 1,000,000,000 bytes.
Benchmark `g` arguments are GiB. The default container target is 48 GiB, with a 50 GiB hard limit,
inside a Linux VM with at least 52 GiB. On a 64 GiB host that leaves 12 GiB outside the VM. Reduce
allocations for a smaller host or heavier background workload.

## Choose the measurement

- `scripts/production-benchmark.py`: Linux cgroup v2, hard limits, no container swap, complete
  container peak including shared pages and charged file cache. Use this for qualification.
- `scripts/performance-benchmark.py`: native Sharrow/non-Sharrow performance comparison. Summed RSS
  can count shared skims repeatedly; USS excludes shared pages. Neither establishes a hard memory
  budget.
- `src/lighthouse/sys_monitor.py`: whole-host resource sampling and progress from the resolved plan
  and main log. It complements the benchmark; it does not isolate model memory.

## Inputs and environment

Use Python 3.10 and `uv sync --locked`. Docker must be running with cgroup v2, memory-limit support,
and at least 2 GiB above the requested container limit. The image installs released dependencies
from `uv.lock` without re-resolving or requiring sibling source repositories.

Supply full households, persons, land use, and OMX skims. `model/data` is a subarea. The revised
`model/data_full` persons must contain `naics_code` for eligible workers. CSV files take precedence
over Parquet fallbacks; keep older versions outside the input directory. Preflight checks schema,
IDs, household membership and sizes, employment/student/industry codes, income, and skim mappings.
It does not modify inputs.

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --preflight-only
```

## Run

The default `--profile laptop` places `configs_explicit_chunk` before the normal configs and uses
Sharrow with recoded zone IDs. `--profile base` explicitly omits that chunk overlay. Lighthouse
extensions are imported by module name for the parent and spawned workers. Thread limits and Linux
allocator settings are recorded in each run specification.

Start with a full-geography integration sample:

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --sample-households 5000 --processes 2 \
  --output-dir model/output/laptop-smoke/timestamp \
  --cache-dir model/output/laptop-smoke-cache
```

Then run the full population in fresh output directories:

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --sample-households 0 --processes 2 4 \
  --memory-limit 50g --qualification-peak 48g --shm-size 16g \
  --output-dir model/output/laptop-qualification/timestamp \
  --cache-dir model/output/laptop-qualification-cache
```

Warm-up compiles Sharrow on a 5,000-household sample and is monitored. `/dev/shm` is a capacity, not
a reservation outside the memory limit. Repeat the chosen worker count with a fresh output
directory; use a fresh cache directory for a cold-cache lifecycle and retain it for a warm repeat.
Do not run competing simulations during qualification. Keep production shadow pricing, checkpoints,
matrix writing, and final output stages enabled.

`--resume` reuses compatible completed jobs and preserves incomplete ones before restarting them. It
is not a checkpoint resume or a new measurement. Input, code/configuration, profile, image,
allocator, and cache identity changes invalidate reuse. Reused rows cannot establish a new pass. The
cache is an execution aid, not evidence of qualification.

## Interpret results

Inspect `report.html`, `metrics.json`, each job's `run-result.json`, `cgroup-samples.csv`,
`host-samples.csv`, `final-cgroup.json`, and `output-validation.json`. Input/code checksums,
effective settings, environment versions, logs, and the resolved run plan accompany the results.

A new qualifying full-population run needs successful execution, valid memory evidence, validated
outputs, a peak within the target, zero container swap, and no OOM or safety stop. Missing
measurements are a failure, not zero memory. Smoke samples and reused results are labeled
unqualified. For full-population invocations, a zero exit status requires a qualifying candidate and
a completed successful requested sweep; inspect the individual results when a sweep is partial.

Whole-container peaks are authoritative. Working-set and component-attributed samples are
diagnostic: subtracting file cache lowers the apparent total, and concurrent components overlap.
Inspect host baseline, headroom, swap growth, and pressure separately. Pre-existing host swap does
not by itself demonstrate swapping caused by the model.

A constrained run on the 128 GiB development Mac establishes a container budget. Final laptop
validation must use the intended OS/runtime on representative 64 GB hardware and check ordinary
interactive responsiveness, host headroom, and sustained swap growth. Do not report a physical
laptop guarantee from the container limit alone.
