# Model tests

The `Model tests` GitHub Actions workflow tests the released dependencies in `uv.lock`. It does not
use `uv-local`, sibling source checkouts, or moving upstream branches. Python 3.10 and the locked
environment are used locally and in CI.

## Run locally

From the repository root:

```sh
uv sync --locked
uv run --locked pytest tests -q
uv run --locked python scripts/model_ci.py --sharrow off --output model/output_ci_off
uv run --locked python scripts/model_ci.py --sharrow require --output model/output_ci_sh \
  --compare-to model/output_ci_off
```

The paired commands write to separate output directories and compare decoded results. Each run
requires a new output directory to prevent stale tables, compiled expressions, or checkpoints from
hiding failures. To repeat:

```sh
uv run --locked python scripts/model_ci.py --output model/output_ci_repeat
uv run --locked python scripts/model_ci.py --households 10000 --output model/output_ci_large
uv run --locked python scripts/model_ci.py --single-process --output model/output_ci_single
```

Output directories matching `model/output*` are ignored. Input and behavioral configuration files
are never rewritten. These commands also work on Windows; hosted model validation is currently
Linux-only.

## What runs in Actions

Every pull request and push to `main` runs input and contract tests and complete model runs for
2,000 households using two workers, once with Sharrow off and once with Sharrow required. The second
run compares its decoded outputs against the first and fails on changed decisions. Logsum
differences are limited to `rtol=1e-5`, `atol=1e-5`; other public attributes must match exactly.
Manual workflow dispatch allows validating a branch before merge. Input checks verify configured CSV
columns, frozen household IDs, skim dimensions, and zone mappings. The contract job checks
formatting of the new test infrastructure; it does not impose a new formatting standard on existing
model files.

On Mondays, and on manual workflow dispatch, two additional jobs run: 10,000 households with two
workers, and the 2,000-household fixture in a single process. Each job compares both backends.
Scheduled runs become active when this workflow reaches the repository's default branch. No larger
paid runner is required for the initial configuration. Full-population performance testing remains
separate.

Only dependency downloads are cached. Model outputs and compiled model caches start fresh. The
workflow cancels superseded runs on a branch and limits job runtime. The artifact and Actions
summary show validation results, distribution comparisons, warnings, elapsed time, versions,
input/configuration hashes, and peak sampled summed process RSS. Summed RSS can double-count shared
pages; it is a sizing diagnostic, not a measurement of unique physical memory. Diagnostics are
retained for 14 days, including logs on failure. Full population outputs and pipeline caches are not
uploaded. PR jobs use read-only repository permissions and need no secrets.

## The fixture

`tests/fixtures/household_ids.json` freezes 10,000 IDs selected by sorting the input household IDs
by SHA256 of `lighthouse-ci-v1:<household_id>`. Routine runs use the first 2,000. All people in
those households are included; all land-use zones and skim matrices remain available. The runner
verifies household size, referential integrity, employment coverage, and the presence of school and
university students. This is an integration fixture, not a statistically representative calibration
sample. Focused component fixtures should exercise uncommon cases.

Keep the ID manifest stable. Changing it, the source population, the seed, or the lockfile can
change results and requires review. CI reads only committed `model/data` files, with no dependency
on local donor data or an external data download. The manifest records selection methodology; it is
not regenerated during tests.

## Failures and advisory results

Blocking checks cover missing/failed model steps, lost population, duplicate IDs, incorrect
household membership, broken person/tour/trip relationships, invalid zone references, missing modes,
invalid time ranges/order, incorrect trip counts, and disconnected trip paths. The component
completion check uses the locked ActivitySim version's timing messages. Updates to its logging
format may require adapting that check.

`tests/test_model_ci.py` deliberately corrupts tiny valid outputs to ensure the validator catches
important failures, including backend comparison failures. The runner loads Lighthouse extensions by
module name so spawned workers can import them. Walking-constraint tests cover its behavioral rules.
`test_skim_backends.py` tests actual skim lookup with intentionally shuffled zone IDs and asymmetric
period-specific values. See [Execution backends](execution-backends.md) for settings and
compatibility fixes. Inputs, shared model configurations, extensions, seed, package versions,
fixture size, and process mode must match before two runs can be compared.

Mode shares, tour-type shares, activity patterns, auto ownership, and output counts are compared
with `tests/baselines/<households>.json`. Changes are **advisory** and cannot fail the build.
Scheduling fallback counts and warnings are also advisory. A known successful run can emit warnings
or error-level diagnostics, so the validator does not equate every such line with a failed model.
Population preservation and completed steps are checked independently.

Baselines describe software behavior, not calibrated forecasts. They were first generated from
`main` at `ec17f0e`, with ActivitySim 1.5.1, Sharrow 2.15.0, seed 0, and two workers on macOS.
Historical distribution changes remain advisory. The separate paired-backend comparison is blocking;
it is not relaxed by these historical baselines. To propose an intentional baseline update, copy a
validated run's `report/distributions.json` to the matching baseline file and review its diff. Never
automatically accept new baselines in CI. Preserve that run's `report/run.json` for provenance in
the PR or its Actions artifacts.

## Extending the tests

Use small explicit component fixtures and derive expected outcomes from agreed model requirements.
For stochastic components, test valid alternatives, probability constraints, fixed-seed
reproducibility, and cases with known expectations. Do not demand exact population shares from a
tiny sample or duplicate the implementation to compute expected values.

Add additional output contracts in `validate_outputs` with a regression test demonstrating that an
invalid output fails. Add distribution metrics in `distributions`; they remain advisory unless an
explicit modeling decision establishes a blocking tolerance. Configure the `contracts` and `model`
jobs as required checks in branch protection after the workflow is merged and established.
