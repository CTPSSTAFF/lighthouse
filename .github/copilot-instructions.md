# Lighthouse agent instructions

These shared instructions apply throughout this repository. Paths below are relative to the
repository root. Edit `AGENTS.md` as the source of truth, then run
`python scripts/sync_agent_instructions.py` to update the Copilot copy.

## Repository context

- Lighthouse is a simplified activity-based travel model built on ActivitySim.
- Python implementation lives in `src/lighthouse`; model configuration and inputs live in `model`;
  exploratory work lives in `notebooks`; operational tools live in `scripts`.
- Read `README.md` and the relevant code and configuration before making changes. Follow existing
  conventions and verify assumptions against the current checkout.
- Use Python 3.10 and uv as specified in `pyproject.toml`. The documented setup is `uv sync --locked`.
  Check `[tool.uv.sources]` first: this checkout references editable sibling ActivitySim and Sharrow
  repositories. Report missing prerequisites; do not silently replace sources or regenerate the lock.

## Working practices

- Inspect Git status before editing. Preserve unrelated changes and untracked files. Scope work to
  Lighthouse unless the task explicitly includes sibling repositories.
- Make focused changes that solve the requested problem. Reuse established abstractions; avoid
  unrelated refactors, new dependencies, and speculative frameworks.
- Keep functions cohesive and names descriptive. Document public behavior and non-obvious reasoning.
  Validate inputs at boundaries and produce actionable errors; do not silently suppress failures.
- Preserve API, configuration, and output compatibility unless the task calls for a change. Explain
  necessary breaking changes and update affected documentation and examples.
- Never commit credentials, private input data, generated model outputs, caches, or notebook output
  accidentally. Do not discard work, rewrite history, push, or publish without task authorization.
- Resolve routine implementation choices independently. Ask when missing domain requirements or
  conflicting requirements would materially change the result.

## Validation

- Add or update focused tests for new behavior and bug fixes. Prefer small deterministic fixtures;
  cover relevant edge cases and failures. Documentation-only changes need document checks, not tests
  that merely repeat their contents.
- Use the formatting and linting rules in `.pre-commit-config.yaml`, including Ruff, yamllint,
  mdformat, and notebook output stripping. Run applicable checks on changed files.
- Use `uv run pytest <test-path>` for relevant tests when available. Do not claim a repository test
  suite exists or passes without locating and running it.
- For model changes, validate relevant input/output schemas, units, identifiers, alignment, and
  invariants. Record seeds and settings for stochastic comparisons. Distinguish intended behavioral
  changes from numerical noise; do not loosen tolerances merely to make a check pass.
- The README documents a model smoke run. Run it when appropriate and inputs are available, using a
  separate output directory to preserve existing results. Match validation cost to the change;
  full production simulations and benchmarks are not mandatory for every edit.
- Review the final diff. Report what changed, checks actually run, and remaining limitations. Never
  describe unrun checks as passing.

## Task-specific instructions

- Before specialized implementation work, consult `docs/agent-tasks/index.md`. Read only guides
  whose stated triggers match the current task, plus references needed for the current step.
- Do not bulk-read task guides, templates, or their supporting references. A task guide supplements
  this baseline only for its stated scope; it does not authorize unrelated actions.
- If a matching guide cannot be opened, report that limitation and request the necessary content
  rather than inventing its requirements. If no guide exists, use this baseline and clarify missing
  domain requirements as needed.
- When maintaining this framework, read `docs/agent-instructions.md`.
