# Fixed work schedule attribute prototype

The `constraint_fixed_work_schedule` step assigns `works_fixed_schedule` to employed nonstudents
using a binary logit with industry intercepts and an income term. It is enabled after
`work_from_home` in both base and multiprocess model sequences. Remote workers are included. All
students are excluded, including students with jobs whose source status is later recoded.

This release assigns an attribute only. It does not draw work hours, reserve time windows, change
tour/trip scheduling, or yet report infeasible schedules. Those consumers remain deferred in the
[component plan](fixed-work-schedule-plan.md). Parameters are explicitly labeled prototype
assumptions, not survey estimates. Survey estimation exports/overrides are not implemented.

## Inputs and utility

Initialization preserves input `pstudent` in `fixed_schedule_source_pstudent` before the existing
student recodes. Eligibility uses source student status, initialized `is_student`, person type, and
employment status. Both full-time and part-time workers contribute to a component-local household
worker count, including employed students and remote workers. The shared `num_workers` is unchanged.

The income proxy is household `income` divided by that worker count. The prototype interprets the
input as annual dollars; the input price year is not documented here. Its coefficient is therefore
not transferable to another income price basis without reviewing/rescaling the parameters.

Utility for `other` is zero; utility for `fixed` is:

`alpha_industry - ln((1 + max(income_proxy, 0) / 50000) / 2)`.

Each industry intercept is the log odds of its
[reference-income probability](fixed-work-schedule-probabilities.md). At income 50,000, those
probabilities are reproduced. Lower income raises probability; the coefficient and scale can be
changed in configuration. `other` does not assert unrestricted scheduling flexibility.

Inputs with missing/invalid eligibility, household joins, eligible-worker income, or industry codes
fail with diagnostics rather than becoming negative predictions. Known excluded people need no
income or industry prediction. Negative income proxies are retained but floored at zero for the
utility transformation, with their count logged. A component-local denominator of zero for an
eligible person is an error. No industry fallback is enabled; all currently eligible industries are
covered.

## Configuration and outputs

Files under `model/configs`:

- `constraint_fixed_work_schedule.yaml`: codes, binary alternative names, income scale/reference.
- `constraint_fixed_work_schedule.csv`: industry indicators and income utility expression.
- `constraint_fixed_work_schedule_coefficients.csv`: industry intercepts and income coefficient.

Expressions use the existing person columns and the prepared income columns. Future explanatory
factors can be added through the specification and coefficients, with input preparation and tests as
needed. The current component uses ActivitySim MNL simulation with the legacy expression evaluator
(`sharrow_skip: true`); it supports standard draws and explicit error terms.

New person outputs:

- `works_fixed_schedule`: nullable Boolean; null for excluded people.
- `fixed_schedule_status`: `prototype_logit`, `not_applicable_student`, or
  `not_applicable_nonworker` (student takes precedence when both exclusions apply).
- `fixed_schedule_probability`: actual simulated probability, null for excluded people.
- `fixed_schedule_household_workers`: the denominator used for eligible people.
- `fixed_schedule_income_proxy`: raw household income per worker for eligible people.
- `fixed_schedule_income_term`: transformed income expression for eligible people.
- `fixed_schedule_source_pstudent`: preserved input student code for all people.

The probability capture uses the framework's native chooser, not a separate random generator. Logs
summarize eligible/excluded counts and expected versus sampled assignments by industry and income
band. Household tracing also exposes utilities and probabilities. Outputs persist through Parquet
checkpoints and final person export. Legacy HDF checkpoint compatibility is not established.

## Running and validation

Use the documented model-directory runner so multiprocess children import `extensions` by module
name. Passing `--ext model/extensions` from the repository root works in a single process but fails
extension import in workers with the currently installed ActivitySim release.

```sh
cd model
uv run --project .. --no-sync activitysim run --ext extensions \
  -c configs_mp -c configs -d data -o /path/to/new/output --households_sample_size 100
```

For focused automated checks, from the repository root:

```sh
uv run --no-sync pytest tests/test_fixed_work_schedule.py -q
```

Implementation validation used the existing Python 3.10 environment without dependency changes. A
local editable-source launcher attempted dependency resolution but could not reach PyPI; tests
instead used the installed ActivitySim environment via `uv run --no-sync`.

A 100-household, seed-0 CLI smoke run executed `initialize_landuse`, `initialize_households`,
`constraint_fixed_work_schedule`, and `write_tables`. A two-worker run used household/person
partitions and coalesced outputs, and a single-process run resumed from `initialize_households`. All
three exported person tables matched exactly, including nullable results and probabilities. The
sample contained 270 people, 125 eligible workers, 77 fixed assignments, and 72.0487 expected
assignments. All 88 source-identified students were excluded. This small realized count is not a
calibration target.

Focused tests cover real specification parsing and probabilities for all industries, the income
response, remote workers, employed students, worker denominators, invalid/empty inputs, row-order
invariance, separate worker processes, explicit error terms, and Parquet persistence. No complete
transport-model run or runtime benefit benchmark was performed; downstream scheduling is unchanged.

The repository-wide run before the final two focused tests reported 71 passed and 38 failed. All
failures were in unchanged `tests/test_sys_monitor.py`; examples include missing `RunPlan`,
`RunMonitor`, and `LogReader` APIs in the unchanged `scripts/sys-monitor.py`. This component does
not modify those files. The final focused run passed all 15 component tests. Ruff lint/format,
strict yamllint on the new settings file, Markdown formatting, and Git whitespace checks also
passed.
