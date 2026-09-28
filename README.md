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

To run the model with test data, use the following command:

```bash
cd model
uv run --project .. activitysim run -c configs_mp -c configs -d data -o ../output-24-2K --ext extensions --households_sample_size 2000
```

## Monitoring

See [Monitoring a model run](docs/sys-monitor.md) for CPU/memory sampling and progress tracking from
ActivitySim run plans and logs.

## Constraint components

See [Fixed work schedule](docs/fixed-work-schedule.md) for the industry/income logit prototype,
configuration, outputs, and validation. Actual work-hour scheduling is deferred.

## Contents

- `model`: ActivitySim inputs (configs, data) for the lighthouse model. Currently `model/data`
  contains test-scale data from CTPS.
- `notebooks`: Demo notebooks to test if the model still works.
- `src/lighthouse`: Python code used to implement this model. This may grow to include extensions to
  ActivitySim for things we want the lighthouse model to do.
