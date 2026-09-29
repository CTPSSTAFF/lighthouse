# Add a constraint component

This guide outlines a workflow; it does not approve any particular constraint specification or
coefficient values. Paths in code spans are repository-root relative.

## Scope and design intent

Use this guide when adding a person or household constraint attribute or substantially changing what
one means. Do not activate it for unrelated components, general cleanup, or routine calibration
under an already agreed specification.

In TDMx, a constraint is a household or person attribute that restricts later choice sets or
directly describes a circumstance affecting later choices. It can represent ability, service
availability, resources, or responsibilities. It need not be binary or deterministic. Adding a
constraint does not imply introducing an optimization solver.

For example, `can_travel_alone` describes an ability, not whether a person actually travels alone on
the simulated day. A fixed-work-schedule attribute describes schedule flexibility, not the actual
departure time. `school_bus_available` describes service connecting home and school, not whether a
student rides the bus. These distinctions let downstream models represent the relevant restrictions
without burying them in indirect utility effects. A caretaker-responsibility measure, for instance,
can explain location preferences more directly than an unexplained demographic proxy.

Constraints can simplify choice sets and improve interpretability, but those benefits depend on the
definition and evidence. Survey responses about ability or responsibilities may be ambiguous, and
observed use does not necessarily identify availability. Do not infer an unavailable option solely
because a respondent did not use it. Explain uncertainty and ask how it should be represented.

Prefer direct, interpretable relationships over unexplained proxies. Keep implementation incremental
and use ActivitySim's extension mechanisms where suitable. Work on a component may produce an attribute now
and integrate it into downstream models later. Ask which scope is wanted; do not automatically
redesign tour generation, scheduling, or mode choice.

## First establish what the user wants

Clarification is part of the task, not an optional courtesy. Read the request and existing
decisions, then ask a small, prioritized group of questions. Begin with meaning, population, and
downstream scope; follow with formulation and data questions once those answers are clear. Do not
present this entire section as a questionnaire regardless of context.

Reuse answers already given. Repository inspection can establish technical facts, but existing code
and worked examples cannot establish the user's intended behavior. Offer options and explain their
effects when helpful, clearly distinguishing recommendations from decisions. Do not select a
behavioral default because it is convenient, common, or present in a donor model. If the user does
not know, help them evaluate the alternatives; do not silently choose for them. Silence is not
confirmation.

Resolve these questions as applicable:

- **Meaning:** What real-world property should the output describe? Does it mean ability or
  availability, actual use, a daily choice, or a longer-term circumstance? What should it explicitly
  not mean? Request a few positive, negative, and ambiguous examples in ordinary language.
- **Population and output:** Is the unit a person or household? Who is eligible? What are the output
  categories, interpretation, and time horizon? Should excluded entities be false, not applicable,
  or another value? Distinguish ineligibility from missing information.
- **Formulation:** Is the intended approach a deterministic rule, a probability assignment, a logit
  model, or a combination? Which conditions are absolute restrictions and which merely change
  likelihood? Ask rather than defaulting to MNL because an example uses it.
- **Evidence and parameters:** What survey, administrative data, borrowed specification, or
  explicitly asserted assumptions support the model? Who supplies thresholds, coefficients, target
  shares, and scenario controls? Is estimation/calibration included, or is a clearly labeled
  prototype wanted? Never invent plausible-looking numbers and describe them as estimated or
  validated. It is acceptable to create an implementation by inventing plausible numbers for
  testing, but you MUST confirm with the user that they agree the numbers are plausible. In
  addition, any invented numbers must be clearly labeled as such with a comment in the same file
  where the numbers are stored, and the user must be informed that they are not validated or
  estimated.
- **Inputs and edge cases:** Which variables and sources are intended? Confirm units, category
  definitions, inclusive/exclusive boundaries, geographic coverage, and treatment of missing or
  invalid values. Ask about proxies before introducing them. Discover actual column names through
  code review.
- **Downstream scope:** Should this task only create and persist the attribute, or also change named
  consumers? For each consumer, should the attribute prohibit an alternative, modify utility, or
  control another rule? What effects are expected when the constraint is relaxed?
- **Acceptance:** Which example outcomes, aggregate comparisons, sensitivity checks, and runtime
  expectations would establish that this component does what the user wants?

Summarize answers in a short component contract: meaning; entity and output; eligibility and missing
data policy; formulation and parameter provenance; inputs and dependencies; downstream scope;
acceptance criteria. Mark unresolved items explicitly and ask the user to confirm the contract
before implementing behavior. Do not repeat this confirmation if the user has already confirmed the
same specification. An explicit delegation of a particular choice permits that choice; record the
delegation and rationale.

While waiting, inspect APIs, locate candidate inputs, and map dependencies. Do not implement or
enable behavior depending on unanswered questions. If the user requests a scaffold before decisions
are made, keep it clearly incomplete and inactive in production configuration. Reopen clarification
if inspection reveals a conflict or a material change to the agreed behavior.

## Map the implementation to the current checkout

After the contract is settled, locate a comparable extension and verify the installed ActivitySim
API. Use the annotated examples below as structural guidance, not as code to copy mechanically.
Inspect `pyproject.toml`, run entry points, configuration layering, and current model lists; do not
change a sibling ActivitySim repository merely to add this component.

Trace every expression input to its producer and the point where it becomes available. Check merged
table broadcasts, person/household keys, school/work location annotations, and required skims. Place
the component after its producers and before any consumers in each applicable run configuration. Do
not copy the examples' position after workplace location without checking the new dependencies. If a
circular dependency emerges, explain it and ask which model relationship should change.

For spatial rules, establish origin/destination fields, zone mappings, distance/time units, skim
name and period, and invalid-location handling. Reuse established annotations where appropriate. An
existing distance column is useful only if its definition matches the agreed constraint.

## Implement the agreed formulation

For a logit extension, the reference structure is:

- `model/extensions/constraint_<name>.py`: settings class and registered `@workflow.step` function.
- `model/extensions/__init__.py`: import the module so registration runs; preserve other
  registrations.
- `model/configs/constraint_<name>.yaml`: specification, coefficients, logit settings, constants,
  and optional preprocessing/annotation settings.
- Corresponding specification and coefficient CSV files, plus a preprocessor only when needed.

Adapt to the current repository rather than imposing these paths if its structure has evolved. For a
simple deterministic rule, use a suitable existing annotation or small extension; unnecessary logit
machinery is not required. Keep scenario parameters in configuration rather than hard-coded Python.

For the logit path, follow the supported sequence: load typed settings, prepare eligible choosers,
apply needed preprocessing, read/evaluate coefficients and specifications, obtain nest settings, and
call the framework simulator with appropriate constants, skims, compute settings, and trace labels.
Use ActivitySim's state-managed random-number facilities; do not substitute global random draws.

Check these details explicitly:

- Specification alternative ordering and configured alternative indices must map to the agreed
  output meaning. Check bounds; do not assume zero means false or that every component is binary.
- CSV expressions must parse with the actual reader, have consistent coefficient names, and use the
  intended category codes. Verify coefficient signs against the intended direction of response.
- A finite negative utility such as `-999` is generally accepted as a proxy for a hard exclusion.
  Implement agreed absolute restrictions using a mechanism whose behavior is verified with the
  current API and specifications. Keep ineligible entities and all-alternatives-unavailable cases
  explicit.
- Handle empty chooser sets without passing them into a simulator that requires nonempty input.
  Preserve original IDs and row alignment when writing results to the base persons/households table.
- Do not use a blanket `reindex(...).fillna(0).astype(bool)` to hide missing predictions or broken
  joins. Apply only the agreed defaults for known excluded entities; detect unexpected missing
  results and validate output dtype and categories, including any survey overrides.
- Persist through the supported state table API and verify the attribute is available to subsequent
  steps. Add useful summaries and household tracing consistent with neighboring components.

When estimation is in scope, retain the framework's settings/specification/coefficient/chooser
exports, simulated choices, survey overrides, and estimation finalization. Verify that survey coding
corresponds to the output and alternatives. Ask how contradictory observed choices or absent survey
values should be handled; do not silently reinterpret them or claim estimation support that has not
been exercised.

## Integrate and validate

Verify extension loading from the actual documented CLI or programmatic entry point. A decorator
alone does not import its module. Check whether `--ext model/extensions` or equivalent loading is
already supplied, including by a prerequisite change, before adding duplicate integration work.

Update applicable single-process and multiprocess model sequences and partition dependencies.
Implement downstream consumption only to the extent agreed in the contract; otherwise document the
intended future consumers and that the attribute currently has no such effect.

Build focused tests from the agreed examples and rules, covering relevant cases:

- Eligible/ineligible entities, threshold boundaries, missing inputs, invalid zones, no eligible
  choosers, and the approved treatment of each.
- Nonconsecutive or reordered IDs, complete result coverage, correct dtype/category mapping, and
  survival of the attribute into a subsequent step.
- Actual settings/specification parsing and expression evaluation with representative inputs; mocks
  alone cannot establish that the CSV/YAML and Python work together.
- Hard restrictions and probability responses tested separately. For probabilistic rules, use fixed
  seeds for repeatability and appropriate probability/aggregate checks rather than expecting every
  individual's sampled result to change monotonically.
- A small end-to-end run through the registered component, plus a representative multiprocess check
  when that mode is supported. Check repeatability under intended execution modes and investigate
  differences rather than immediately relaxing expectations.
- Estimation exports/overrides when supported, and downstream effects only when included in scope.

Run applicable lint/format checks. A configured hook is not proof that CI or local hooks execute it.
Report precisely which checks ran and what missing data or infrastructure prevented. Separate
software correctness from behavioral validation: a successful run does not establish that assumed
coefficients are credible.

Deliver the implementation with its agreed contract, parameter provenance, configuration/run
instructions, validation results, and remaining limitations. Identify deferred consumers and
unestimated parameters explicitly. Do not describe a prototype as a calibrated production component.

## Annotated implementation examples

These examples are part of this guide and require no external reference material. Read the
subsection relevant to the agreed formulation. They illustrate a binary person-level component;
adapt the entity, categories, and mechanics to the confirmed contract. They are teaching fragments,
not a complete component ready to enable. Verify API signatures against the installed ActivitySim
version: Lighthouse owns the maintenance of its extensions when those APIs change.

### Settings and registration

Keep filenames, workflow name, trace label, output name, and estimation name consistent. For
example, `constraint_can_travel_alone` is a workflow name, while `can_travel_alone` is its person
attribute.

```python
import pandas as pd
from pydantic import Field

from activitysim.core import config, expressions, simulate, workflow
from activitysim.core.configuration.logit import LogitComponentSettings


class ConstraintCanTravelAloneSettings(LogitComponentSettings, extra="forbid"):
    # Required: make the mapping visible in YAML rather than assuming it.
    CAN_TRAVEL_ALONE_ALT: int = Field(ge=0)


@workflow.step
def constraint_can_travel_alone(
    state: workflow.State,
    persons: pd.DataFrame,
    persons_merged: pd.DataFrame,
    model_settings: ConstraintCanTravelAloneSettings | None = None,
    model_settings_file_name: str = "constraint_can_travel_alone.yaml",
    trace_label: str = "constraint_can_travel_alone",
) -> None:
    if model_settings is None:
        model_settings = ConstraintCanTravelAloneSettings.read_settings_file(
            state.filesystem, model_settings_file_name
        )
    # Continue with the agreed eligibility, simulation, and persistence logic.
```

`extra="forbid"` helps catch misspelled settings. The base class provides settings for
specification, coefficients, constants, logit structure, preprocessing, annotations, and compute
options. Add typed fields for additional component-specific settings rather than silently ignoring
them.

In `model/extensions/__init__.py`, an explicit re-export preserves the import's registration side
effect and makes its intent clear to unused-import checks:

```python
from . import constraint_can_travel_alone as constraint_can_travel_alone
```

Append to existing imports. Defining or listing a workflow step does not load its module. From the
repository root, a CLI invocation using this layout includes `--ext model/extensions`, for example:

```sh
uv run activitysim run --ext model/extensions \
  -c model/configs_mp -c model/configs -d model/data -o model/output_constraint_check
```

Use a fresh output directory and verify the extension-loading convention in the installed version.
For a programmatic runner, ensure extension imports occur before executing the workflow. Do not
assume that successful manual import proves the documented runner or a worker process loads the
extension.

### A specification and coefficient file that agree

This **synthetic test fixture** demonstrates a two-alternative MNL and its mapping. It is not a
plausible behavioral specification. Its equal utilities are chosen to make mechanics easy to
inspect. Do not enable it as model behavior; any proposed behavioral test values still need the
user's explicit agreement and labels in their files.

`constraint_can_travel_alone.yaml`:

```yaml
# SYNTHETIC TEST FIXTURE ONLY: not estimated, calibrated, or approved for model use.
SPEC: constraint_can_travel_alone.csv
COEFFICIENTS: constraint_can_travel_alone_coefficients.csv
LOGIT_TYPE: MNL
CAN_TRAVEL_ALONE_ALT: 0  # Index among alternative columns, excluding metadata columns.
CONSTANTS: {}
```

`constraint_can_travel_alone.csv`:

```csv
Label,Description,Expression,can_travel_alone,cannot_travel_alone
util_asc,SYNTHETIC TEST ONLY equal utility reference,@1,0,coef_cannot_asc
```

`constraint_can_travel_alone_coefficients.csv`:

```csv
# SYNTHETIC TEST FIXTURE ONLY: zero is a mechanics test value, not an estimate.
coefficient_name,value,constrain
coef_cannot_asc,0,T
```

The first three spec columns describe the term; the remaining columns are alternatives. Here the
first alternative, index 0, maps to `True`. Reversing those columns without updating the setting
reverses the output's meaning. `@1` is a constant expression. The coefficient name in the spec must
exactly match the coefficient table. Verify comment handling with the actual CSV reader. The
`constrain` field controls estimation treatment of the parameter; it is not a chooser eligibility
flag.

In this fixture the two utilities are equal, so an MNL gives each alternative probability 0.5. A
finite sample need not split exactly in half. A positive `coef_cannot_asc` raises the probability of
the `cannot_travel_alone` alternative, not the probability of `can_travel_alone`.

When adding age effects, put agreed cutoffs in `CONSTANTS`, reference them by name, and ensure
labels describe exact boundaries. For example, this optional row describes a half-open age band:

```csv
util_age_band,Age at least AGE_LOWER and less than AGE_UPPER,@(df.age>=AGE_LOWER)&(df.age<AGE_UPPER),0,coef_age_band
```

`AGE_LOWER`, `AGE_UPPER`, and `coef_age_band` deliberately have no behavioral values in this guide.
Ask for them or propose values for confirmation. A positive value on this row increases the relative
likelihood of inability within the band. Do not automatically reuse such a relationship for another
constraint or substitute an age proxy when the agreed input is a directly measured ability.

### Preparing choosers and simulating

The following fragment belongs inside a step after settings are loaded and eligibility is resolved.
`eligible` is a validated Boolean Series indexed like `persons_merged`, computed from the confirmed
rules. Missing eligibility is an unresolved input, not automatically false. `estimator` is the
active estimation object or `None`, initialized before coefficient evaluation when estimation is
supported.

```python
constants = model_settings.CONSTANTS or {}
choosers = persons_merged.loc[eligible].copy()
expressions.annotate_preprocessors(
    state,
    df=choosers,
    locals_dict=constants,
    skims=None,
    model_settings=model_settings,
    trace_label=trace_label,
)
spec = state.filesystem.read_model_spec(file_name=model_settings.SPEC)
coefficients = state.filesystem.read_model_coefficients(model_settings)
spec = simulate.eval_coefficients(state, spec, coefficients, estimator)
positive_alt = model_settings.CAN_TRAVEL_ALONE_ALT
if not 0 <= positive_alt < len(spec.columns):
    raise ValueError("CAN_TRAVEL_ALONE_ALT does not identify a spec alternative")

choices = pd.Series(index=choosers.index, dtype="int64")
if not choosers.empty:
    choices = simulate.simple_simulate(
        state,
        choosers=choosers,
        spec=spec,
        nest_spec=config.get_logit_model_settings(model_settings),
        locals_d=constants,
        estimator=estimator,
        trace_label=trace_label,
        trace_choice_name="can_travel_alone",
        compute_settings=model_settings.compute_settings,
    )
```

Using a copy keeps temporary preprocessing columns off the shared merged table. If eligibility
depends on a preprocessed value, compute that value before selecting choosers. `skims=None` is
appropriate only when expressions need no skim wrappers; supply the necessary wrappers to
preprocessing and simulation when the agreed model uses them. Ensure preprocessing also handles an
empty frame, or bypass it when appropriate. Skip the simulator for empty populations or partitions.

The simulator returns alternative positions, not the final Boolean attribute. Validate the returned
index, missing values, and positions before comparison; otherwise an invalid value can silently
become `False`. In this binary example, both alternative positions must be known and valid.

### Persisting by ID without concealing missing predictions

The following continuation assumes the contract explicitly says excluded people receive `False`. It
does not prescribe that policy for other components. `choices` contains only the eligible
predictions.

```python
if not persons.index.is_unique or not choosers.index.is_unique:
    raise ValueError("Person IDs must be unique")
if not choosers.index.isin(persons.index).all():
    raise ValueError("Chooser IDs are missing from persons")
if (
    not choices.index.is_unique
    or len(choices) != len(choosers)
    or not choosers.index.isin(choices.index).all()
):
    raise ValueError("Predictions do not cover exactly the eligible person IDs")
choices = choices.reindex(choosers.index)
if choices.isna().any() or not choices.isin(range(len(spec.columns))).all():
    raise ValueError("Missing or invalid alternative positions")

predicted = choices.eq(positive_alt)
# Apply validated estimation overrides here, if estimation is active.
result = pd.Series(False, index=persons.index, dtype=bool)
result.loc[predicted.index] = predicted
updated_persons = persons.copy()
updated_persons["can_travel_alone"] = result
state.add_table("persons", updated_persons)
```

If excluded or unknown people require a nullable result instead, implement that confirmed policy and
verify consumers can handle it. An ID mismatch must not become a normal negative outcome through
`fillna(0)`. For example, predictions indexed `[42, 7]` must still map to the right people when the
base table order is `[7, 42]`; reset-index or positional assignment can produce believable but wrong
results.

After persistence, produce a value-count summary, log eligible/excluded counts, and use household
tracing when configured. Apply configured result annotations through `expressions.annotate_tables`
after the new base table is available; verify that a subsequent merged-table read sees the
attribute.

### Estimation hooks

When estimation is included, initialize it before evaluating coefficients:

```python
from activitysim.core import estimation

estimator = estimation.manager.begin_estimation(state, "constraint_can_travel_alone")
```

Before simulation, export the settings, symbolic specification, coefficient table, and prepared
choosers using the installed estimator API. A typical form is:

```python
if estimator:
    estimator.write_model_settings(model_settings, model_settings_file_name)
    estimator.write_spec(file_name=model_settings.SPEC)
    estimator.write_coefficients(coefficients, file_name=model_settings.COEFFICIENTS)
    estimator.write_choosers(choosers)
```

After converting valid alternative positions to the output coding, write simulated choices and
obtain the observed override before persistence:

```python
if estimator:
    estimator.write_choices(predicted)
    observed = estimator.get_survey_values(predicted, "persons", "can_travel_alone")
    # This example assumes the confirmed survey coding is Boolean or numeric 0/1.
    if not observed.index.equals(predicted.index):
        raise ValueError("Survey override IDs do not match simulated choices")
    if observed.isna().any() or not observed.isin([False, True]).all():
        raise ValueError("Survey overrides require the agreed Boolean coding")
    predicted = observed.astype(bool)
    estimator.write_override_choices(predicted)
    estimator.end_estimation()
```

Do not cast strings such as `"False"` directly to Boolean; nonempty strings can become true. Other
survey coding requires an explicit mapping. Agree on handling observed violations of hard
restrictions and missing observations before implementation. The export/override lifecycle supports
estimation; it does not itself estimate coefficients or establish their validity.

### School-bus service and dependency ordering

First ask whether the desired attribute represents physical service coverage, eligibility to use
that service, or likelihood of riding it. For physical coverage, home and school locations and the
service relationship between them are central. Home area type and distance may be approved
approximations when coverage data are unavailable, but they are not automatically equivalent to
actual service coverage. Household vehicle availability may help explain usage; using it to explain
physical coverage needs a separate, explicit rationale.

Resolve age versus enrollment eligibility, grade-school versus high-school inclusion, the service
boundary and distance measure, and the treatment of missing school assignments. Do not choose an age
ceiling or radius simply because a worked example needs one. Confirm whether boundaries are
inclusive. Category codes in the current configuration distinguish grade school and high school; a
K–12 expression using those constants would include both:

```python
is_k12 = persons_merged.school_segment.isin(
    [constants["SCHOOL_SEGMENT_GRADE"], constants["SCHOOL_SEGMENT_HIGH"]]
)
```

Verify that these constants are actually passed to the expression context. `school_segment == 1`
alone does not represent both categories when grade school is 1 and high school is 2. Also
distinguish the `school_segment` codes from other student-status fields whose categories may differ.

A row such as the following changes utility within a radius; it does not make locations outside the
radius unavailable:

```csv
Label,Description,Expression,school_bus,no_school_bus
util_distance,Distance below the agreed radius,@df.distance_to_school<SERVICE_RADIUS,coef_within_radius,0
```

Ask whether distance should define an absolute boundary, change a probability, or stand in for
missing coverage data. With this column ordering, a positive coefficient favors school-bus
availability within the radius; a negative one disfavors it. Check that this is the intended
response. Define the units of both distance and radius and the treatment of invalid or absent
destinations before evaluating it.

The existing school-location configuration can annotate `distance_to_school` from home and school
zones using the `DIST` skim; household initialization can annotate home area type. Inspect those
definitions before adding duplicate preprocessing, and verify they execute in the target run.

The input household table may already contain `auto_ownership`, and `auto_ownership_simulate` may
later replace it. Ask which version the model requires. If the confirmed specification uses
**simulated** ownership, the relative sequence must place its producer first, for example:

```yaml
# Relative ordering only; preserve other required workflow steps.
models:
  - school_location
  - workplace_location
  - auto_ownership_simulate
  - constraint_school_bus_availability
```

If it uses imported ownership, document that meaning instead. If auto ownership is itself intended
to consume bus availability, the dependency can become circular; ask the user which relationship is
intended rather than rearranging steps until the run succeeds. Apply the agreed order to relevant
single-process and multiprocess configurations, including partition boundaries and merged-table
inputs.

### Exclusion penalties and boundary tests

A configured unavailable-utility coefficient of `-999` is an accepted modeling convention for
approximating a hard restriction. Retain it where agreed and verify its actual effect: an additive
penalty interacts with other utility terms, and assigning it to every alternative does not identify
a valid choice. Test that restricted alternatives cannot be selected under the intended
specification and scenario range. If exact exclusion is required, verify the chosen mechanism
guarantees it.

For any agreed age or distance cutoff, test values just below, exactly at, and just above the
cutoff. Keep unknown data separate from those boundary cases. For a logit, inspect computed
probabilities as well as sampled choices; one seeded draw cannot prove that an availability
restriction is enforced.
