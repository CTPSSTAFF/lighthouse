# Running with or without Sharrow

Lighthouse supports two configurations, following the overlay pattern in
[ActivitySim's MTC example](https://github.com/ActivitySim/activitysim-prototype-mtc/tree/extended/configs_sh).
The base configuration uses original zone IDs; the Sharrow overlay enables compilation and recoding
together. Do not toggle only one of these settings.

- `model/configs`: `sharrow: false`, `recode_pipeline_columns: false`.
- `model/configs_sh` over the base configs: `sharrow: require`, `recode_pipeline_columns: true`.

The non-Sharrow skim dictionary maps original zone IDs through the OMX mapping. With recoding
enabled, it instead uses zero-based positions; those are only correct if the land-use order matches
OMX storage. Lighthouse's inputs have different orders. Sharrow explicitly realigns the skim dataset
to land-use zone IDs before switching to recoded indices, so recoding is both required and safe on
that path. Input files do not need to be reordered or rewritten.

## Commands

Lighthouse requires ActivitySim 1.6 or newer and Sharrow 2.16.2 or newer. The lockfile currently
selects ActivitySim 1.6.0 and Sharrow 2.16.2.

From the Lighthouse repository root, with the locked environment installed:

```sh
# Multiprocessing settings come from configs_mp; base evaluation uses NumPy/pandas.
uv run --locked activitysim run -c model/configs_mp -c model/configs \
  -d model/data -o model/output_numpy --ext extensions

# Put the Sharrow overlay ahead of the other configuration directories.
uv run --locked activitysim run -c model/configs_sh -c model/configs_mp -c model/configs \
  -d model/data -o model/output_sharrow --ext extensions
```

For a single-process run, omit `-c model/configs_mp`. Use separate, fresh output directories for
each run; do not resume an old checkpoint with a different backend or recoding configuration.
Outputs from both modes decode origins, destinations, and assigned locations back to source zone
IDs.

`--ext extensions` is required for Lighthouse's constraints, telework components, and safe skim
loading. The `skim_loading` extension retains the single-worker Dask guard introduced after
concurrent PyTables/HDF5 reads crashed during realignment with Sharrow 2.15. This does not limit
ActivitySim's worker processes or change compiled utility expressions.

Destination **sampling** uses the reference evaluator in both modes: small differences in compiled
cumulative probabilities can move a random draw across a sample boundary and change downstream
locations. Logsum and final-choice evaluation still compile. This is an explicit subcomponent
setting, not an automatic compiler fallback. The existing scheduling exclusions remain in place.

The school-bus and tour/trip mode specifications disable fast-math because their inputs can contain
NaN school distances or infinite walking limits. Strict IEEE semantics preserve the NumPy comparison
behavior. The model also now supplies the child-count column referenced by telecommute frequency and
removes leading whitespace rejected by the CDAP expression compiler. Behavioral coefficients are
unchanged.

The documented `python uv-local` runner can replace `uv run --locked` for sibling-source
development. ActivitySim 1.6 supports the additional trip-mode chunk budget in
`model/configs_explicit_chunk`; add that directory before the other configs to opt in. This setting
was isolated because ActivitySim 1.5.1 rejected it. It remains optional and is not included in base
configuration or CI runs. The other existing component chunk settings remain in place.

## Backend stability checks

```sh
uv run --locked pytest tests -q
uv run --locked python scripts/model_ci.py --sharrow off --output model/output_ci_off
uv run --locked python scripts/model_ci.py --sharrow require --output model/output_ci_sh \
  --compare-to model/output_ci_off
```

Both runs use the same frozen 2,000-household fixture, seed 0, and two workers. The comparator
aligns decoded households, people, tours, and trips by ID and requires identical choices, schedules,
locations, capability flags, and all other non-logsum attributes. Only logsum columns permit
floating-point roundoff (`rtol=1e-5`, `atol=1e-5`); the report records the maximum absolute
difference for each. Missing entities, mismatched columns, changed decisions, and larger logsum
discrepancies fail CI. Internal `_original_` columns created solely by recoding are excluded.

PR/main CI runs this pair. Scheduled/manual jobs also compare the larger fixture and the
single-process fixture. The ordinary historical distribution baselines remain advisory; they are not
substituted for the blocking backend comparison. Old distributions from the incorrectly recoded
non-Sharrow configuration are not a valid geographic reference for the corrected runs.

The CI runner gives each run a fresh compiled-expression cache and a separate shared-memory skim
name. It also verifies matching input/configuration/extension hashes, seed, package versions,
household fixture size, and process mode before accepting a comparison.

`tests/test_skim_backends.py` additionally loads an intentionally shuffled, asymmetric OMX fixture
through each actual backend and verifies origin/destination and time-period values against known
answers. This catches mapping mistakes even when a stochastic model run happens to select the same
modes. Model startup also exercises required compilation rather than allowing silent fallback.

## Validation of this configuration

Before the dependency upgrade, local validation with locked ActivitySim 1.5.1 and Sharrow 2.15.0
passed all 56 contract tests. Cold-cache, two-worker backend comparisons passed for both the
2,000-household and 10,000-household fixtures (seed 0). All non-logsum outputs matched exactly; the
largest absolute logsum differences were approximately 2.44e-6 and 2.63e-6, respectively. The larger
pair produced 27,049 tours and 69,400 trips in each backend. The scheduled single-process pair is
configured in CI but was not included in these local full-fixture comparisons.

With ActivitySim 1.6.0 and Sharrow 2.16.2, all 56 contract tests passed again. The cold-cache,
two-worker 2,000-household comparison (seed 0) also passed: every non-logsum attribute matched
exactly, and the largest absolute logsum difference was approximately 2.44e-6. The larger and
single-process fixtures were not rerun locally for this dependency upgrade.
