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

## Developing with local ActivitySim and Sharrow checkouts

Install Git, Python 3.10 or newer, and uv, with `git` and `uv` available on your PATH. From the
Lighthouse repository root, run:

```sh
python scripts/make-developer-env.py
```

On macOS/Linux, use `python3` if that is your Python command. On Windows, `py -3` also works.
The setup script uses only Python's standard library. uv selects Python 3.10 for the model according
to `pyproject.toml` and can download it if needed.

The script clones the ActivitySim and Sharrow repositories from the ActivitySim GitHub organization
into sibling directories when they do not already exist:

```text
parent-directory/
  lighthouse/
  activitysim/
  sharrow/
```

Existing sibling Git checkouts are reused without pulling, switching branches, or discarding edits.
New clones use each repository's default branch. You can select other compatible branches yourself.
If a sibling path exists but is not a suitable checkout, setup stops rather than replacing it.

Setup creates `uv-local` and adds `/uv-local` to this checkout's Git exclude file. It does not change
`pyproject.toml`, `uv.lock`, or `.gitignore`. Running setup again is safe: it reuses the clones,
refreshes its generated runner, and avoids duplicate exclude entries. Customize the generator if
needed, since rerunning setup replaces edits to a generated runner. An unrelated file named
`uv-local` is left alone and reported as an error. The earlier local shell runner is migrated to
the Python runner automatically.

Use the runner instead of `uv run` for local source development:

```sh
python uv-local python -c "import activitysim, sharrow; print(activitysim.__file__); print(sharrow.__file__)"
python uv-local activitysim run -c model/configs_mp -c model/configs -d model/data -o model/output
python uv-local jupyter lab
```

`python uv-local` works on macOS, Linux, and Windows; macOS/Linux also support `./uv-local`.
Commands run from the Lighthouse root, and their arguments and exit status are preserved. Start
Jupyter through the runner to use these sources in its inherited environment.

The first invocation installs the locked project environment and an editable overlay for the sibling
packages. Source paths take precedence over released packages in the base environment. Local changes
are available on subsequent imports; restart a running Python process or notebook kernel when needed.
The project lockfile stays unchanged, but the sibling overlay is resolved from those checkouts and is
not pinned by Lighthouse's lockfile. Incompatible dependency versions can therefore cause a run to
fail. Ordinary `uv run` continues to use the locked project dependencies.

The `Developer environment` GitHub Actions workflow tests setup on macOS, Linux, and Windows,
including repeated setup, preservation of existing work, real sibling imports, and editability.
Run its offline tests locally with:

```sh
python -m unittest discover -s tests -p test_developer_env.py
```

## Contents

- `model`: ActivitySim inputs (configs, data) for the lighthouse model. Currently `model/data`
  contains test-scale data from CTPS.
- `notebooks`: Demo notebooks to test if the model still works.
- `src/lighthouse`: Python code used to implement this model. This may grow to include extensions to ActivitySim for things we want the lighthouse model to do.
