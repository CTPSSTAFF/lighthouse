# lighthouse

This is a light-weight, simplified ABM.

## Usage

This project uses uv as Python manager. To install uv, please visit https://docs.astral.sh/uv/getting-started/installation/

Once uv is installed on the machine, create a new Python environment for lighthouse and install dependencies.

```bash
uv sync --locked
```

To run the model with test data, use the following command:

```bash
uv run activitysim run -c model/configs_mp -c model/configs -d model/data -o model/output
```

## Contents

- `model`: ActivitySim inputs (configs, data) for the lighthouse model. Currently `model/data`
  contains test-scale data from CTPS.
- `notebooks`: Demo notebooks to test if the model still works.
- `src/lighthouse`: Python code used to implement this model. This may grow to include extensions to ActivitySim for things we want the lighthouse model to do.

## Automated model tests

GitHub Actions runs contract tests and the complete model on a fixed 2,000-household sample,
using the released dependencies in `uv.lock`. Structural failures block the checks; changes
in modeled distributions are reported for review. Weekly and manual runs also test a larger
sample and single-process execution.

```sh
uv sync --locked
uv run --locked pytest tests -q
uv run --locked python scripts/model_ci.py
```

See [Model tests](docs/testing.md) for fixtures, output checks, diagnostics, and baseline updates.
