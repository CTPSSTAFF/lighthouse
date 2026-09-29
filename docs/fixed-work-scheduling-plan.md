# Fixed work-hour assignment and scheduling integration

Status: design for review; no scheduling behavior is implemented by this change. The existing
industry/income logit continues to determine who has a recurring fixed schedule.

## Recommendation

Use a shared catalog of approximately 32 work start/end pairs and a separate probability table by
industry and employment status. This implements the proposed finite distribution directly and is
easier to inspect than estimating another scheduling logit without survey evidence.

The distribution is `P(schedule | fixed worker, industry, full-/part-time status)`. It does not
repeat the probability of being fixed. Draw the pair jointly, once per person, and persist it across
transport scenarios. Each working day has one work episode. Being assigned a recurring schedule does
not, by itself, force work attendance every day.

Use two runtime input files:

- `fixed_work_schedule_alternatives.csv`: `schedule_id`, `work_start_minute`, `work_end_minute`,
  `end_day_offset`, and a descriptive label. Use minutes after local midnight, even if the initial
  catalog uses whole hours. Duration is derived, not independently sampled.
- `fixed_work_schedule_probabilities.csv`: `naics_code`, `employment_status`, `schedule_id`,
  `probability`. Include all supported industry/status segments explicitly. Each sums to one; absent
  alternatives mean zero, but an absent segment is an error. Include parameter provenance and
  assumption labels in metadata/comments.

There are 25 current industry codes and two employed statuses, so a dense 32-alternative table is
only 1,600 rows. A sparse long-format table will usually be shorter. Use shared profile templates
when authoring assumptions, then expand them to explicit runtime probabilities; a third runtime
profile hierarchy is unnecessary initially. Keep equal defaults for manufacturing 31/32/33 and
retail 44/45 unless evidence supports distinctions. Codes 99 and blank are not worker industries.

A continuous start-time/duration model or a new scheduling logit adds estimation and validation work
without clear prototype benefits. The finite catalog can later be expanded or populated from survey
work episodes without changing the integration contract.

## Initial catalog: 32 distinct pairs

All times below are unvalidated prototype candidates within the confirmed daytime/evening scope. The
catalog is shared: a pair can receive positive probability for either employment status. These are
work-obligation intervals, not home departure/return times, and not necessarily paid hours.

- Ten ordinary day shifts: 06–14, 06–15, 07–15, 07–16, 08–16, 08–17, 09–17, 09–18, 10–18, 10–19.
- Four long day shifts: 06–16, 07–17, 07–19, 08–20.
- Four later shifts: 11–19, 12–20, 13–21, 14–22.
- Twelve short shifts: 06–10, 07–11, 08–12, 09–13, 10–14, 11–15, 12–16, 13–17, 14–18, 15–19, 16–20,
  18–22.
- Two intermediate shifts: 09–15, 15–21.

Full-time workers should receive mostly 8–9-hour intervals with selected 10–12-hour shifts.
Part-time workers should receive mostly 4–6-hour intervals, but some probability of 8-hour or longer
workdays. Part-time status describes weekly hours, not necessarily short daily shifts; the
[BLS definition](https://www.bls.gov/cps/definitions.htm) makes this distinction. Existing model
`pemploy` codes determine the segment; do not infer or change that status from the sampled duration.

For this prototype, schedule distributions apply to the modeled workday rather than a newly modeled
weekly roster. Multiple jobs, split shifts, and multiple work locations within a day are outside the
one-episode specification.

## Industry-specific assumptions to develop

These directions are modeling judgments, not measured distributions. The examples refer only to
workers already classified as recurring-fixed, including remote workers. Do not use the overall
industry distribution of flexible or rotating shifts as if it were conditional on fixed status.

- **11 Agriculture:** favor 06–14/06–15/07–15 for full time; morning blocks such as 06–10/07–11 for
  part time. Seasonal variation remains outside the initial weekday prototype.
- **21 Mining and 22 Utilities:** mix early/ordinary operating shifts and some long shifts; part
  time mostly morning/day blocks, with some full-length days.
- **23 Construction:** concentrate full time at 06–15/07–15/07–16; part time at 07–11/08–12/09–15.
- **31/32/33 Manufacturing:** favor 06–14/07–15 plus a meaningful 14–22 shift; part time morning and
  afternoon blocks. Recurring night shifts need explicit overnight support later.
- **42 Wholesale:** blend early distribution shifts and 08–17 office/service hours; part time
  primarily morning/day blocks.
- **44/45 Retail:** spread full time across 08–17/09–18/10–19/12–20/13–21; part time spread across
  midday, afternoon, and evening coverage rather than concentrated at 09–13.
- **48 Transportation and 49 Postal/courier/warehousing:** favor early and later operating shifts,
  with longer day shifts represented; part time morning and afternoon/evening blocks.
- **51 Information:** mostly 08–17/09–17/09–18, with some later operations; part time mostly day
  blocks. Its broad industry coverage does not justify an exclusively office-hours distribution.
- **52 Finance, 54 Professional/scientific/technical, and 55 Company management:** concentrate on
  08–17/09–17/09–18; part time 08–12/09–13/13–17/09–15, with some full-length days.
- **53 Real estate/rental:** blend office and extended customer-service shifts; part time mostly
  midday/afternoon with an evening tail.
- **56 Administrative/support/waste:** broad mixture of early collection, day support, and later
  cleaning/security schedules; part time should retain both early and evening blocks.
- **61 Education:** concentrate full time at 07–15/08–16/08–17; part time at 08–12/09–13/09–15.
  Education includes more than teachers; keep an alternative tail rather than imposing one bell
  time.
- **62 Health care/social assistance:** mix 07–15/08–16/08–17 clinics and care, 07–19/08–20 long
  shifts, and 14–22 coverage; part time primarily short/intermediate blocks with some long days.
- **71 Arts/entertainment/recreation:** mix day facility staffing with 12–20/13–21/14–22; part time
  favor afternoon/evening, retaining morning/day facility roles.
- **721 Accommodation:** early/day/later coverage, including 06–14/08–16/14–22; part time morning
  housekeeping/service and evening blocks.
- **722 Food service:** mix 06–14 breakfast/daytime, 10–18/11–19 daytime service, and 14–22 evening
  coverage; part time emphasize 10–14/11–15 and 16–20/18–22.
- **81 Other services:** blend 08–17/09–17/10–18 with later customer service; part time mostly
  day/afternoon blocks and a modest evening tail.
- **92 Public administration:** mostly 08–16/08–17/09–17 with some operating shifts; part time
  mostly morning/day blocks. This broad sector includes more than office work.

As a concrete example for review, education full time could use 07–15 at 60%, 08–16 at 30%, and
08–17 at 10%; education part time could use 08–12 at 35%, 09–13 at 35%, 09–15 at 20%, and 08–16 at
10%. These are invented illustrative probabilities, not approved parameters or survey estimates.
Prepare the remaining numerical rows as the next review artifact before enabling assignment.

The
[BLS 2017–18 schedule overview](https://www.bls.gov/spotlight/2020/job-flexibilities-and-work-schedules/)
supports considering both daytime and non-daytime work and distinguishing full/part time. Its
population and schedule categories do not establish the exact conditional probabilities proposed
here. Survey identification remains deferred.

## What must change around mandatory scheduling

The current model has 190 tour departure/return alternatives, with hourly values from 05:00 through
23:00. `mandatory_tour_scheduling` passes all mandatory tours to `run_tour_scheduling`, which
evaluates schedule utilities/logsums, assigns timetable windows, and writes `tdd`, `start`, `end`,
and `duration`. A new extension wrapper can partition the tours and call that existing helper only
for the remaining nonfixed work and school tours, keeping their existing specs and tracing labels.
Avoid replacing the shared tours table with a temporary subset or editing the sibling ActivitySim
source.

However, simply removing fixed workers from that call is insufficient:

1. **Assign the recurring work interval early.** Add a person-level draw after fixed status is
   assigned, before daily duration/tour generation. Persist schedule ID and work start/end
   separately from tour times. Do not redraw in response to congestion, mode, or other activities.
1. **Reconcile the modeled workday.** Keep work attendance separate from schedule status. A working
   fixed person has one episode, at home or at work; a nonworking day has no active reservation. The
   current `telework_arrangement` can indicate in-home work while a work tour is also possible. Add
   a mutually exclusive daily arrangement for fixed workers before generating tours. A proposed
   prototype rule is that a planned on-site workday uses the single on-site episode and suppresses
   additional home work; otherwise an indicated home-work day uses the remote episode. This priority
   needs review; do not silently assume the current independent outputs are consistent.
1. **Enforce one episode before creating tours.** The existing mandatory frequency alternatives
   include `work2` and `work_and_school`. For fixed, nonstudent on-site workdays, generate `work1`
   directly; for home-work days generate no work tour. Do not generate two tours and delete one
   afterward, which would leave frequency attributes, IDs, and counts inconsistent. School-only or
   combined commitments for this population are contract violations, not competing fixed schedules.
1. **Use fixed hours for remote duration.** Exclude these workers from stochastic
   `telework_duration` and derive their duration from the assigned interval. Reserve their at-home
   work interval in the person timetable without inventing a commuting tour.
1. **Replace the mandatory scheduling workflow entry with an extension wrapper.** Reserve fixed
   remote obligations and schedule fixed work tours first. Filter only work tours whose person has
   `works_fixed_schedule == True` (nullable exclusions must not count as fixed). Send the remaining
   mandatory tours through the existing scheduler. Merge outputs by tour ID, preserving every row,
   expected column, and timetable checkpoint. Never pass an empty set to a simulator requiring rows.
1. **Constrain later choices.** Nonmandatory activity generation and scheduling must respect the
   remaining time, with a no-activity outcome when no alternative fits. Joint participation and
   escorting cannot impose conflicts on fixed workers. The confirmed initial break policy blocks the
   entire work interval, including at-work lunch and errand subtours. Restrict their frequency to
   no-subtours for these workers.

All fixed-hour reservations must happen before other flexible activities for these people are
scheduled, including remote workers who have no mandatory tour. School scheduling remains unchanged
for the excluded student population.

## Work hours versus travel times

For work from 08:00 to 16:00, 08:00 is the required work start, not departure from home. The
commuter must arrive by 08:00 and cannot leave work before 16:00. Earlier arrival may require
waiting; the worker's required hours do not move. A remote worker reserves 08:00–16:00 with no
travel buffers.

Tour scheduling currently precedes mode choice, stop generation, and trip scheduling. To guarantee
feasibility, downstream modes and stop chains must respect work arrival/departure anchors; ordinary
tour start/end bounds alone do not enforce them.

Recommended prototype approach for review:

- Assign the work interval exogenously first. Enumerate a small set of feasible direct-commute
  timing options using time-dependent travel estimates for candidate modes. This step must not
  choose another work interval to accommodate congestion.
- Reserve a conservative travel-and-work envelope spanning those viable mode/timing options in the
  existing timetable. Round the reservation outward to the current hourly grid; preserve minute work
  anchors separately. A mode that cannot reach this fixed interval within the model horizon is
  unavailable. If no mode works, record infeasibility rather than shifting the work interval.
- Restrict final mode and stop-chain choices to the reserved envelope and work anchors, and validate
  final trip arrival/departure times. Stops are allowed only if they fit before work arrival or
  after work departure. Other activities cannot reclaim unused buffer time until feasibility is
  proven.
- This conservative reservation may suppress some otherwise feasible optional activities. Quantify
  that loss; a later refined joint mode/timing treatment can reduce it. A universal one-hour or
  auto-only buffer would not guarantee feasibility across modes and should not be presented as such.

A focused implementation spike must verify timetable interval semantics, time-dependent skim lookup,
mode availability, and final trip timing before selecting exact buffer/rounding rules. If enforcing
these anchors requires reordering fixed-tour mode choice, document that narrower change explicitly.
The wrapper alone can demonstrate the scheduling bypass but must not be called full enforcement.

## Model horizon, breaks, and infeasibility

The initial catalog fits inside the current daytime horizon, but commutes can still fall outside it.
Real night shifts such as 22–06 or 19–07 cannot be represented by setting `end < start` in the
existing tour alternatives. Supporting them requires extending time windows and auditing skim-period
mapping, trip timing, exports, and day-boundary treatment. The file schema includes a day offset for
future support; the initial runtime must reject unsupported offsets rather than silently drop or
move them.

Confirmed by the user: daytime/evening prototype first, explicitly defer overnight shifts, and block
the entire work episode against at-work subtours. These choices limit coverage for manufacturing,
transportation, care, hospitality, and other overnight industries. Neither limitation is evidence
that those workers do not exist. A catalog conditioned on in-horizon schedules is a restricted
prototype, not a complete all-shift population representation.

Preserve the earlier infeasibility contract: few or no failures are expected, since fixed work is
scheduled first and other choices are constrained around it. Record person/household/schedule IDs,
work anchors, proposed travel/tour bounds, stage, reason, and scenario/seed. Distinguish invalid
inputs, unsupported horizon, no feasible commute, inconsistent workday/tour count, and downstream
violations. Report zero counts explicitly. An optional activity correctly excluded for lack of time
is not an infeasible work schedule. Never redraw a shift to hide a failure.

## Review and implementation milestones

1. Review the catalog/data schema, numerical probability example, and remote/on-site
   daily-arrangement rule. Daytime/evening scope and blocking the entire work interval are
   confirmed. Produce the complete industry-by-status probability table for review before using
   invented weights in model behavior.
1. Implement validated inputs, person-level schedule draws, and persistence, with distributions
   tested independently of transport conditions. This creates no claim of downstream enforcement.
1. Integrate one-episode tour generation and remote duration/reservation, then add the mandatory
   scheduling wrapper. Preserve the original nonfixed path and deterministic random streams.
1. Complete mode/trip/stop feasibility integration and no-activity handling. Test the conservative
   envelope and final work anchors before enabling the complete workflow.
1. Run single-process, multiprocess, resume, and scenario comparisons. Measure scheduling logsum
   evaluations, runtime, buffer-related activity suppression, and infeasibility counts. Compare
   nonfixed outcomes with the baseline where their inputs/time windows are unchanged.

Tests must cover all 50 industry/status segments, probability normalization/unknown IDs, full-time
and part-time durations, employed-student exclusion, no-work days, remote-only work, prohibited
multiple work tours, incompatible home/on-site outputs, all-fixed/all-nonfixed/empty populations,
correct person/tour joins and nullable flags, exact timetable reservations, arrival/departure
boundaries, congestion-invariant work anchors, infeasibility capture, and stable draws across
supported execution modes. No schedule probabilities should depend on transport utilities.
