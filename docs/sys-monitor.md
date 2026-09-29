# Monitoring a model run

`sys_monitor.py` samples CPU and memory usage and tracks ActivitySim progress using the resolved
`run_list.txt` and the main `activitysim.log`. It discovers model names, phase membership, and
expected worker counts from the run plan. Adding a component or splitting/renaming a phase requires
no monitor code changes.

```bash
uv run python src/lighthouse/sys_monitor.py \
  --log model/output/log/activitysim.log \
  --csv model/output/log/sys_usage.csv
```

Use the actual log location for your logging configuration; some runs put logs directly in the
output directory. By default, the monitor looks for `run_list.txt` next to `--log`. Override this
with `--run-list PATH`. Use the main process log, not an individual worker's log. The CSV parent
directory must already exist.

The monitor can start before the files exist or attach during a run. It replays existing log history
once, then reads appended lines, retaining incomplete lines until the writer finishes them. It
replays again when the plan changes and resets execution evidence if the log is replaced or
truncated. `--tail-bytes` remains accepted, but now controls the read chunk size, not the amount of
history retained. A small value no longer loses early completions or worker starts. Replaying a
large existing log can delay the first resource sample being displayed.

Existing `--interval`, `--delay`, `--parent-pid`, and `--csv` options and CSV columns are preserved.
Worker counts are now available for every phase, including phases with one worker. `--parent-pid`
stops sampling after the parent exits, after reading available final log records; exit does not
itself mean the model succeeded.

## Interpreting progress

The displayed step is the earliest model step not yet satisfied by all workers expected by the plan.
It is not necessarily the step occupied by every worker: one worker can finish several steps before
another starts. Worker counts come from resolved `num_processes`, not just observed start messages.
Repeated completion messages do not count twice. Model order is a step count, not a time-based
percentage or ETA.

The status values are:

- `unknown`: the run plan or log is missing, unreadable, or unsupported. Resource sampling continues
  with blank step/worker fields and a diagnostic; the monitor retries automatically.
- `waiting`: a plan is available but execution has not yet been observed.
- `resuming`: a resumed phase has workers whose restored progress is not yet known. The displayed
  step is the earliest unproven step, not a claim that the worker is executing it.
- `running`: execution has been observed and some planned work remains.
- `finalizing`: all model steps are satisfied, but overall success has not been logged. Coalescing
  or other finalization can still fail.
- `finished`: the main log contains ActivitySim's successful overall timing record.
- `failed`: the main log reports a subprocess failure or an unrecoverable run error. Later timing
  records cannot turn that failure into success.

## Resumes

The adapter reads the saved breadcrumb snapshot in `run_list.txt`, not the live `breadcrumbs.yaml`
that ActivitySim updates while running. Phases already marked simulated are satisfied. Workers saved
as completed are credited only for a phase resuming with `_`; a named checkpoint can deliberately
rerun workers that finished previously.

The monitor does not assume that a requested checkpoint is the checkpoint actually restored. For a
resumed worker, a completion of a later model proves that its earlier phase models were either run
or restored. A successful worker-exit message also satisfies that worker's phase. Until such
evidence arrives, partial resume progress may remain unresolved. Single-process tracking
additionally reads the runner's resolved `resume_after` message.

## Format and compatibility limits

The adapter targets ActivitySim's `print_run_list()` text format, checked against ActivitySim 1.5.1
and a local development run. This format is informational, not ordinary YAML: it contains repeated
`step:` blocks and Python-style breadcrumb values. The parser deliberately rejects incomplete phase
coverage, invalid worker counts, unknown resume workers, and duplicate model names rather than
silently reporting misleading progress. Repeated invocations with identical model names are not
supported; distinct execution names including arguments are retained.

Single-process tracking accepts a corresponding `multiprocess: False` run plan. ActivitySim entry
points do not all write a single-process `run_list.txt`; supply one exported from the actual
resolved run configuration with `--run-list` if it is available. The monitor does not reconstruct
settings or substitute a multiprocess plan. Without a plan it continues resource sampling with
unknown progress.

Use matching run-plan and log files from the same invocation, preferably in a separate output
directory. The text artifacts have no common invocation identifier, so the monitor cannot reliably
detect every stale/mismatched pair or recover evidence removed before it attaches. Custom logging
formats that omit logger names or completion messages may leave progress unresolved. Use a separate
log per invocation rather than appending multiple invocations to one file.

A supported replacement for this adapter has been requested in
[ActivitySim issue #1120](https://github.com/ActivitySim/activitysim/issues/1120): a versioned JSON
manifest of the resolved run plan. This implementation does not assume an unimplemented JSON schema.

## Focused tests

```bash
uv run pytest tests/test_sys_monitor.py
```

The small synthetic fixtures cover new components, renamed phases, staggered and one-worker
execution, late attachment, named and last-checkpoint resumes, single-process logs, failures,
partial writes, and log replacement. They do not require a model simulation or input data.
