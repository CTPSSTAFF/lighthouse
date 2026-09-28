# Proposed constraint: works a fixed schedule

Status: revised plan for review. No model behavior or configuration has been changed.

## Confirmed component contract

Represent employed nonstudents who work the same recurring required schedule across days. Their
required work hours cannot change in response to transportation prices, incentives, accessibility,
or congestion. Future consumers must enforce those hours as hard restrictions.

- Workflow step: `constraint_fixed_work_schedule`.
- Person attribute: `works_fixed_schedule`.
- Eligible population: employed nonstudents, including full-time and part-time workers and remote
  workers. Travel to work is not required.
- Excluded population: all students, including students with jobs, and all nonworkers.
- Assignment: binary logit with industry and personal income as the initial explanatory factors. Use
  household income divided by household workers as the temporary personal-income proxy.
- Available information: existing input fields only. Occupation and direct flexibility responses are
  not available and are not required for the prototype.
- Initial implementation: assign and persist the attribute only. Actual work-hour draws and
  downstream enforcement are deferred.
- Evidence path: build a prototype using explicitly documented reasonable assumptions, then validate
  and revise it using survey evidence when available. Survey content is currently unknown.
- Scheduling priority: fixed work will be the only fixed-schedule commitment for these workers.
  Other activities and travel must fit around it; they cannot create conflicting obligations.

The attribute does not mean that a person works today, commutes, uses a particular mode, or leaves
home at a fixed time. A remote employee can have fixed hours without any work tour. Congestion can
require earlier travel without changing work hours.

Employer-assigned rotating or variable shifts do not qualify merely because a particular day's hours
are mandatory. A negative result means no recurring fixed schedule under this definition; it does
not establish unrestricted freedom to change work hours. Teachers, nurses, factory workers, and
retail workers motivate the component but are not deterministic classification rules.

## Eligibility and current inputs

The person input configuration retains `pemploy`, `pstudent`, `ptype`, and `naics_code`, plus
demographic and household fields. Employment and student status determine eligibility. Household
income and worker counts now also supply the authorized personal-income proxy. Remote status does
not directly enter utility.

Initialization derives `is_worker` from full-time and part-time employment. `work_from_home` later
sets `is_out_of_home_worker`. Do not use commuting status as an eligibility condition.

There is an important integration issue in `model/configs/annotate_persons.csv`: initialization
recodes some student statuses, including setting full-time worker person types to nonstudent. Using
only the resulting `is_student` could admit students with jobs. Preserve source student status
before these recodes and combine it with recognized student person types and initialized student
status for exclusion. A source student must remain excluded even if later annotations classify the
person as a worker. Validate missing or conflicting eligibility fields explicitly rather than
silently treating unknown student status as nonstudent. This preservation is local to the new
component's eligibility and does not require redesigning existing student models.

Proposed output representation remains a nullable Boolean plus a status/source field:

- Eligible and assigned: true or false, with assignment source marked as prototype industry draw.
- Known excluded: null and not-applicable status, with student/nonworker counts reported.
- Unresolved input: unknown status, distinct from both not-applicable and an assigned false result.

Exact output coding and the policy for unresolved input remain implementation contract details for
review. The attribute-only release has **no downstream scheduling effect**.

## Binary logit assignment

The user has authorized replacing industry-only probability assignment with a logit that supports
multiple explanatory factors. Initially use industry and personal income; retain the agreed
eligibility and transportation-invariance rules. Do not add other predictors without a
specification.

For eligible person i in industry j:

- `U_other = 0`.
- `U_fixed = alpha_j + beta_income * x_income`.
- `P_fixed = 1 / (1 + exp(-U_fixed))`.

Here `other` means not recurring-fixed under the component definition, not unrestricted flexibility.
Use ActivitySim's binary MNL machinery and state-managed random draws. Give each industry an
intercept with no additional common intercept, avoiding redundant parameters. Keep coefficients and
income transformation constants in configuration. Export utilities/probabilities and assignment
summaries by industry and income band for review.

Proposed prototype income specification, not yet approved or estimated:

- `y = max(person_income_proxy, 0)` in annual input dollars.
- `x_income = ln((1 + y / 50000) / 2)`.
- `beta_income = -1.0`.
- `alpha_j = ln(p_j / (1 - p_j))`, where p_j is the previously proposed industry probability.

At an income of 50,000, the income term is zero and the earlier industry probability is recovered.
Lower income raises fixed-schedule probability; higher income lowers it. The logarithm keeps zero
income defined and moderates the high-income tail. These constants and the slope are explicit
prototype assumptions for review, not empirical results. The industry probabilities now describe a
reference-income person, not unconditional industry averages. The previous 59.5% industry-only
aggregate therefore does not describe the new model and is not a calibration target.

### Personal income proxy and denominator

The user authorizes household income divided by household workers as the temporary proxy. There is
no person earnings field in the current inputs. Keep the derived value named as a proxy and record
its source so a future observed/synthetic person-income field can replace it. Confirm the annual
dollar basis and price year before behavioral activation; adjust the reference and scale
consistently when income units change. Do not silently mix dollars from different years.

A read-only audit found that 327 eligible people live in households with supplied `num_workers = 0`.
Among households containing eligible people, 56,951 supplied worker counts differ from counts of
person records with `pemploy` full-time or part-time. Confirmed resolution: compute a
component-local household worker count from those person records for every household. Include
employed students and remote workers in this denominator even though students are excluded from
assignment. Do not divide by the count of eligible nonstudent workers. Do not overwrite the shared
household worker count.

The denominator must be a positive integer for any eligible person; fail with IDs if that invariant
is broken. Missing income must be reported rather than treated as zero. There are 157 eligible
people with zero household income in the inspected inputs and no negative-income eligible cases.
Propose flooring future negative proxy incomes at zero, with counts reported; this is a modeling
assumption, not correction of the source data. Preserve raw and transformed values for diagnostics.
The person-record denominator is confirmed. Negative/missing-income handling remains proposed for
review.

The proxy assigns equal income to employed members of a household and can include household nonlabor
income. It does not estimate their separate wages. When individual income arrives, retain its
provenance and reconsider the slope and intercepts rather than assuming proxy coefficients transfer
unchanged.

### Industry inputs and stability

Validate industry mapping and coefficient coverage; missing, malformed, or unmapped codes must not
silently become the reference industry or an assigned false result. The
[industry probability proposal](fixed-work-schedule-probabilities.md) supplies reference-income
probabilities and logit conversion details; none of its numerical parameters are approved yet.

Keep status stable across transportation scenarios with the same people, industry/income inputs,
configuration, and seed. No transport skims, costs, logsums, or simulated-workplace predictors enter
utility. Input or coefficient changes are explicit socioeconomic assumptions.

## Prototype now, survey validation later

Separate two future data products:

1. Industry and income coefficients for recurring fixed-schedule status among employed nonstudents.
1. Joint distributions of required work start and end times for those assigned fixed schedules.

The prototype does not depend on identifying a survey or its questions now. Design replaceable
configuration tables so assumed coefficients and, later, assumed schedule distributions can be
replaced without changing the component's interface. No survey acquisition or estimation is included
in the first attribute implementation.

When suitable survey data become available, assess whether they identify recurring fixed schedules,
validate industry/income relationships, shares, and schedule patterns using appropriate weights, and
revise assumptions. A single observed work time does not by itself establish recurrence or inability
to change hours. The validation method and any pooling of sparse industries must follow the actual
survey content; do not promise labels or variables that are not yet known to exist.

## Deferred work-hour assignment and enforcement

Define a versioned schedule-distribution interface with industry/group, schedule identifier,
required work start and end, applicable workdays/day type, overnight day offset, and probability or
weighted count. Keep units, time-period conversion, source, and assumptions explicit. Validate
coverage, weights, durations, and model-day compatibility. Jointly draw start and end to preserve
realistic durations. Draw the recurring pattern once and reuse it on applicable modeled workdays;
attendance is separate. Do not redraw fixed hours in response to transport conditions.

Assign work obligations independently of whether work tours exist. Remote workers reserve the
required work interval at home; commuting workers additionally require feasible travel to and from
work. Split shifts, overnight work, and multiple jobs need either explicit episode-pattern support
or a documented unsupported-case diagnostic; do not silently truncate them.

Treat fixed work as the first scheduling obligation. For eligible workers there will be no other
fixed-schedule commitments. Other activity participation, timing, duration, and associated travel
must be restricted to the remaining feasible choices. An optional activity with no feasible slot
must not be generated or must be omitted through an explicit no-activity outcome, rather than
relaxing fixed work or accepting a conflict. Coordinate household participation where relevant so
other household members cannot introduce conflicting obligations for the fixed worker.

The current `mandatory_tour_scheduling` step chooses tour periods before tour mode choice and later
trip scheduling. Required work hours are not the same as tour departure/return periods. A focused
integration design must map work hours, travel times, modes, and stops to feasible tour periods,
reserve person time windows, and maintain feasibility through final trips. Never write required work
start/end directly into tour `start`/`end` without this mapping. Workers outside this component
retain their existing path; this does not assert that every excluded worker is behaviorally
flexible.

Observed downstream tour schedules may eventually inform efficient proposal draws, but alone they do
not guarantee fixed work hours under changed travel times. Convert and validate their meaning before
use. Precompute distributions offline rather than creating a circular dependency on the current
downstream simulation.

## Infeasibility capture and reporting

The design expectation is few to no infeasible schedules: a fixed work obligation should be feasible
by itself, and all remaining activities and travel are constrained around it. For commuters, verify
that the work-only baseline includes feasible access/return travel within the model horizon; for
remote workers it includes the work interval without a commute.

Provide a structured diagnostic record with person/household ID, schedule ID, relevant tour/trip
IDs, failed stage, reason code, required interval, available interval or travel-time requirement,
and scenario/seed/configuration version. Report totals and rates among fixed workers, by industry
and reason, including an explicit zero count when none occur.

Distinguish invalid schedule inputs, unsupported work patterns, infeasible work-only travel, and
violations introduced by downstream scheduling. An optional activity correctly ruled unavailable is
not an infeasible fixed schedule; report those exclusions separately if useful. Never silently move
work hours, redraw until convenient, or export conflicting schedules as valid. Proposed prototype
policy: preserve diagnostics and fail validation on unexpected conflicts; choose the eventual
run-level failure handling during downstream integration.

## Implementation milestones

1. **Complete plan review and propose prototype parameters.** Retain the confirmed definition,
   eligibility, industry-plus-income logit formulation, and attribute-only scope. Review proposed
   coefficients, income transformation, and coding/missing-data policies before behavioral
   implementation.
1. **Implement the attribute prototype.** Add `model/extensions/constraint_fixed_work_schedule.py`,
   typed YAML settings, binary MNL specification and coefficient CSVs, income preprocessing,
   eligibility preservation, validation, framework random draws, persistence, and summaries. Import
   the extension in `model/extensions/__init__.py`. Update both `model/configs/settings.yaml` and
   `model/configs_mp/settings.yaml` after verified initialization inputs and before consumers. No
   workplace location dependency or scheduling modification is needed.
1. **Test and review the prototype.** Verify software behavior and distributions against configured
   assumptions. Mark results as unvalidated; survey absence does not block this prototype.
1. **Later: assign schedules and enforce them.** Supply assumed joint schedule distributions,
   complete the travel-time integration design, reserve work first for remote and commuting workers,
   constrain remaining choices, and add infeasibility reporting and final-trip validation.
1. **Later: validate with survey evidence and benchmark.** Replace assumptions as supported by the
   eventual survey. Measure scheduling and total-run savings after downstream integration.

Use existing ActivitySim extension mechanisms without modifying the sibling ActivitySim repository.
Final persons/tours are already configured for output; verify new fields survive exports,
checkpoints, merged-table reads, and multiprocess boundaries. No runtime speedup is claimed from the
attribute step alone. Savings should come later from bypassing preference-based work-hour
utility/logsum calculations for fixed workers while retaining necessary travel-feasibility and mode
calculations.

## Acceptance criteria

For the attribute prototype:

- Remote and on-site employed nonstudents are eligible; students with any employment status are
  excluded, including source students whose status is recoded during initialization.
- At equal industry and income, probabilities are equal regardless of other person attributes.
  Within each industry, probabilities decrease as income rises for a negative income coefficient.
  Reference-income probabilities match the industry anchors, and a zero income coefficient recovers
  the industry-only formulation. Test probabilities rather than individual sampled monotonicity.
- Test the proxy with multiple workers, employed students, remote workers, zero income, and invalid
  inputs. Verify component-local denominator counts and household-to-person alignment.
- Actual table/YAML parsing, probability bounds, industry coverage, missing-data policy, empty
  populations, person-ID alignment, output coding, registration, and persistence all work correctly.
- Assignments are repeatable across supported execution modes, restarts, and row order using
  framework random streams. Transportation-only scenario changes leave them unchanged.
- Realized industry/income shares match summed logit probabilities within sampling tolerances;
  diagnostics distinguish prototype consistency from empirical validation.

For later scheduling integration:

- Required recurring work hours remain unchanged across transportation scenarios. Remote obligations
  are enforced without requiring a tour; commuter travel adjusts within work-hour constraints.
- All other activities and travel fit around fixed work, with no accepted conflicts or final-trip
  violations within the explicitly approved time resolution.
- Infeasibility reporting handles zero cases and deliberately constructed failures, with sufficient
  information to reproduce each failure. Excluded optional activities are counted separately.
- Benchmark assignment overhead, work-scheduling runtime/logsum evaluations, total runtime, and
  memory on comparable samples/seeds; set performance targets after a baseline measurement.

## Remaining review details

- Prototype industry intercepts, income slope/transformation, and industry grouping; numerical
  assumptions are proposed in the linked review document but are not approved or validated.
- Nullable output/status coding and explicit handling of unknown eligibility or industry.
- Later only: identical hours on all workdays versus a repeating weekly pattern, time resolution,
  allowed arrival windows, supported work patterns, and run-level handling of unexpected
  infeasibility.

Survey identity and content, occupation data, and competing fixed commitments are not prerequisites
or unresolved requirements for the initial component.
