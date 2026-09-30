# Restricted memory performance measurement

The target is a complete model run on a machine with 64 GB RAM, with room for its operating system and
background applications.

## Choose the measurement

- `scripts/production-benchmark.py`: Use Docker (which must be available and running), Linux cgroup
  v2, hard limits, no container swap, complete container peak including shared pages and charged
  file cache. Use this for qualification.
- `scripts/performance-benchmark.py`: native Sharrow/non-Sharrow performance comparison. Summed RSS
  can count shared skims repeatedly; USS excludes shared pages. Neither establishes a hard memory
  budget.
- `src/lighthouse/sys_monitor.py`: whole-host resource sampling and progress from the resolved plan
  and main log. It complements the benchmark; it does not isolate model memory.

## Inputs and environment

Use Python 3.10 and `uv sync --locked`. For `production-benchmark`, Docker must be running with
cgroup v2 and memory-limit support. The image installs the versions recorded in `uv.lock`;
no sibling source repositories are needed.

GB and GiB are different units: 1 GiB is about 1.074 GB. The commands below use these tested limits;
the `g` suffix means GiB:

| Setting | Tested value | Approximate GB |
| --- | ---: | ---: |
| Docker VM memory allocation | 52 GiB | 55.83 GB |
| Model hard limit (`--memory-limit`) | 48.5 GiB | 52.08 GB |
| Passing peak (`--qualification-peak`) | 47 GiB | 50.47 GB |

Set the VM allocation in Docker Desktop before running. Our 52 GiB allocation provided 50.89 GiB
of usable Linux memory, leaving over 2 GiB above the model limit. On a 64 GiB machine, that VM
allocation leaves 12 GiB for the operating system and other applications. Check actual RAM before
using these settings on a machine advertised as 64 GB. Keep the explicit command limits below:
the script defaults are higher (50 GiB hard limit and 48 GiB passing peak).

Supply full households, persons, land use, and OMX skims, which are not included in the Git repo; the
included `model/data` is only a subarea. Preflight checks schema,
IDs, household membership and sizes, employment/student/industry codes, income, and skim mappings.
It does not modify inputs.

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --preflight-only
```

## Run

The default `--profile laptop` places `configs_explicit_chunk` before the normal configs and uses
Sharrow with recoded zone IDs. `--profile base` removes these memory controls and may require
substantially more RAM; whether it runs faster must be measured. Lighthouse extensions are imported
by module name for the parent and spawned workers. Thread limits and Linux allocator settings are recorded in each run specification. The laptop overlay sets these absolute
chunk targets (ActivitySim divides them across workers):

| Component | `explicit_chunk` |
| --- | ---: |
| School location | 25,000 |
| Workplace location | 10,000 |
| Nonmandatory tour destination | 10,000 |
| At-work subtour destination | 10,000 |
| Nonmandatory tour scheduling | 20,000 |
| Trip destination | 2,000 |
| Trip mode choice | 100,000 |

The upstream workplace fraction grows with population. Its sampler, and the larger nonmandatory
destination chunk, exceeded the laptop limit at full scale. Smaller fixed targets bound those
utility matrices; the school setting adds headroom for simultaneous worker allocations.

The laptop overlay also sets `location_logsum_rows: 100000` in `laptop_memory.yaml`.
Lighthouse batches school, workplace, nonmandatory, at-work, and trip destination logsum joins before
ActivitySim materializes person attributes for sampled alternatives. Internal utility chunking alone
does not bound those joins. Trip batches also restrict the trip-to-tour join before expanding
sampled alternatives, preserving both out-of-direction logsums. The batches preserve positional
sample order and keep every chooser's alternatives together,
including broadcast preprocessor random draws. A batch may exceed the row target by the remaining
alternatives for its last chooser. Destination sampling and shadow-pricing iterations are unchanged. The base profile
keeps the upstream path. This compatibility extension is specific to the locked ActivitySim version;
recheck its interfaces and output parity when upgrading.

Stop frequency also projects the person attributes listed in `laptop_memory.yaml` before joining
them onto tours. This avoids creating the complete wide `tours_merged` table. The original
stop-frequency implementation still sees all tours, so its person and household tour counts are
unchanged. Update that column list and run the fixture comparison when changing stop-frequency
specifications or preprocessing.

For trip destination, failed-trip retries, and trip mode choice, the laptop profile builds
`tours_merged` using the declared trip-mode/logsum chooser columns before the join. It retains all
tour attributes, including origin and destination. It takes the required attributes directly from
persons and households when available, releases the cached wide temporary person join, and avoids
unnecessary input copies for this pure join. Earlier models and the base profile retain the full join. Recheck this compatibility
extension when upgrading ActivitySim or adding models that consume the temporary table.

Start with a full-geography integration sample:

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --sample-households 5000 --processes 2 \
  --memory-limit 48.5g --qualification-peak 47g --shm-size 16g \
  --output-dir model/output/laptop-smoke/timestamp \
  --cache-dir model/output/laptop-smoke-cache
```

Then run the full population in fresh output directories:

```sh
uv run --locked python scripts/production-benchmark.py \
  --data-dir model/data_full --sample-households 0 --processes 2 4 \
  --memory-limit 48.5g --qualification-peak 47g --shm-size 16g \
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

## Measured results

The full population (3.60 million households and 8.67 million people) completed these tests on
September 30, 2026. Use **four workers** with the limits above for the tested configuration.

| Workers | Compilation cache | Peak RAM | Full-run time |
| --- | --- | ---: | ---: |
| 4 | Newly prepared | 47.50 GB | 2 h 18 m |
| 4, fresh repeat | Reused | 50.23 GB | 2 h 18 m |
| 2 | Reused | 47.43 GB | 3 h 19 m |

Allow another two to six minutes for the separate warm-up. All runs passed output checks without
running out of memory or using container swap. The repeated four-worker runs produced identical
final model tables. The highest peak was only 0.24 GB below the passing target, so keep these
limits and retest after changes to the model or inputs.

These tests used model commit `2abb9bf`, its locked dependencies, and Docker on a 128 GiB ARM Mac.
They establish the model's memory use; operation on a physical 64 GB machine has not yet been tested.
