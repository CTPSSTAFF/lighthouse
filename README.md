# lighthouse

This is a light-weight, simplified ABM.

## Usage

This project uses uv as Python manager. To install uv, please visit
https://docs.astral.sh/uv/getting-started/installation/

Once uv is installed on the machine, create a new Python environment for lighthouse and install
dependencies.

```bash
uv sync --locked
```

If running multi-processor, then need to disable multi-threading (once per session)
```bash
$env:MKL_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMBA_NUM_THREADS = "1"
```

To run the model with test data, use the following command:

```bash
cd model
uv run --project .. activitysim run -c configs_mp -c configs -d data -o ../output-24-2K --ext extensions --households_sample_size 2000
# run all households in the test data
# uv run --project .. activitysim run -c configs_mp -c configs -d data -o output --ext extensions
```

## Monitoring

See [Monitoring a model run](docs/sys-monitor.md) for CPU/memory sampling and progress tracking from
ActivitySim run plans and logs.

For a full-population run on a 64 GB laptop, see [memory qualification](docs/laptop-memory.md).
The production benchmark enforces a container limit, disables container swap, validates inputs
and outputs, and records the complete container memory peak. The ordinary README smoke command
uses the smaller subarea inputs and does not establish full-scale memory requirements.

## Constraint components

See [Fixed work schedule](docs/fixed-work-schedule.md) for the industry/income logit prototype,
configuration, outputs, and validation. Actual work-hour scheduling is deferred.

## Contents

- `model`: ActivitySim inputs (configs, data) for the lighthouse model. Currently `model/data`
  contains test-scale data from CTPS.
- `notebooks`: Demo notebooks to test if the model still works.
- `src/lighthouse`: Python code used to implement this model. This may grow to include extensions to ActivitySim for things we want the lighthouse model to do.


## Development

To point to a local repo, add this to the pyproject.toml file with path to your ActivitySim repo
[tool.uv.sources]
activitysim = { path = "C:/projects/activitysim", editable = true }
