# Add a constraint component

This guide outlines a workflow; it does not approve any particular
constraint specification or coefficient values. Paths in code spans are repository-root relative.

## Scope and design intent

Use this guide when adding a person or household constraint attribute or substantially changing what
one means. Do not activate it for unrelated components, general cleanup, or routine calibration
under an already agreed specification.

In TDMx, a constraint is a household or person attribute that restricts later choice sets or
directly describes a circumstance affecting later choices. It can represent ability, service
availability, resources, or responsibilities. It need not be binary or deterministic. Adding a
constraint does not imply introducing an optimization solver.

Prefer direct, interpretable relationships over unexplained proxies. Keep implementation incremental
and use ActivitySim's extension mechanisms where suitable. The design document explicitly permits
producing an attribute now and integrating it into downstream models later. Ask which scope is
wanted; do not automatically redesign tour generation, scheduling, or mode choice.

## First establish what the user wants

Clarification is part of the task, not an optional courtesy. Read the request and existing
decisions, then ask a small, prioritized group of questions. Begin with meaning, population, and
downstream scope; follow with formulation and data questions once those answers are clear. Do not
present this entire section as a questionnaire regardless of context.

Reuse answers already given. Repository inspection can establish technical facts, but existing code
and example PRs cannot establish the user's intended behavior. Offer options and explain their
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
  likelihood? Ask rather than defaulting to MNL because the example PRs use it.
- **Evidence and parameters:** What survey, administrative data, borrowed specification, or
  explicitly asserted assumptions support the model? Who supplies thresholds, coefficients, target
  shares, and scenario controls? Is estimation/calibration included, or is a clearly labeled
  prototype wanted? Never invent plausible-looking numbers and describe them as estimated or
  validated. It is acceptable to create an implementation by inventing plausible numbers for testing,  
  but you MUST confirm with the user that they agree the numbers are plausible. In addition, any
  invented numbers must be clearly labeled as such with a comment in the same file where the numbers 
  are stored, and the user must be informed that they are not validated or estimated.
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
API. Use available examples as a structural examples, not as code to copy mechanically.  
Inspect `pyproject.toml`, run entry points, configuration
layering, and current model lists; do not change a sibling ActivitySim repository merely to add this
component.

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

- `model/extensions/constraint_<name>.py`: settings class and registered `@workflow.step` function.on.
- `model/extensions/__init__.py`: import the module so registration runs; preserve other registrations.
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
- A finite negative utility such as `-999` is generally accepted as a proxy for a hard exclusion. Implement
  agreed absolute restrictions using a mechanism whose behavior is verified with the current API and
  specifications. Keep ineligible entities and all-alternatives-unavailable cases explicit.
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
alone does not import its module. Check whether `--ext model/extensions` or equivalent loading is already
supplied, including by a prerequisite change, before adding duplicate integration work.

Update applicable single-process and multiprocess model sequences and partition dependencies.
Implement downstream consumption only to the extent agreed
in the contract; otherwise document the intended future consumers and that the attribute currently
has no such effect.

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

## Source rationale

Read [source notes](constraint-component-sources.md) when checking the design rationale,
interpreting the example PRs, or revising this draft. They distinguish document recommendations,
human review, observed implementation patterns, and additional safeguards proposed by this guide.
