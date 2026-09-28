# Proposed industry anchors for the fixed-work-schedule logit

Status: proposal for user review, not approved or enabled. All probabilities below are invented
prototype assumptions, not survey estimates or validated parameters. Census sources support the
industry meanings only, not these probabilities or the behavioral reasoning.

## Definition and population

A positive assignment means the same recurring required work start/end schedule across days, which
the worker cannot change in response to transportation conditions. Merely working regular hours by
preference is insufficient. Employer-controlled but changing rosters are not automatically recurring
fixed schedules. Remote workers are eligible on the same basis as on-site workers. All students,
including employed students, are excluded.

Inventory taken from `model/data/persons.csv` on 2026-09-28. Employment means `pemploy` 1 or 2;
student exclusion uses source `pstudent` 1 or 2 or student person types `ptype` 3, 6, 7, or 8. This
preserves source student status before initialization recodes it.

The file contains 1,074,799 people, 500,629 eligible workers, and 81,183 employed students excluded
by this rule. All eligible workers have one of the 25 industry codes listed below. Counts are input
person records, not survey-weighted estimates.

The current industry values are imputed test inputs, as documented in
[the data README](../model/data/README.md). They are not observed individual industries. The
imputation preserves 721/722, uses other two-digit prefixes, and maps 3MS to 33 and 4MS to 45.
Consequently these are model industry buckets, not uniformly standard two-digit sectors. Use equal
probabilities within 31/32/33 and within 44/45 rather than inventing precision from those splits.

## Proposed assumptions

Each probability applies only after eligibility is established. Reasoning below is modeling judgment
for review, not an empirical claim about measured shares. Rates use five-percentage-point increments
to avoid suggesting false precision.

- **11 — Agriculture, forestry, fishing and hunting: 40%**. Eligible workers: 1,761. Allow for
  regular crews, but seasonal, weather-driven, and owner-operated work reduces recurring fixed
  hours.
- **21 — Mining, quarrying, and oil and gas extraction: 65%**. Eligible workers: 169. Assume many
  coordinated shifts, with an allowance for rotating rosters and variable field work.
- **22 — Utilities: 70%**. Eligible workers: 3,262. Assume substantial scheduled operations and
  service coverage; allow for on-call and emergency work.
- **23 — Construction: 75%**. Eligible workers: 26,203. Assume coordinated crew start/end times
  predominate; allow for weather, project changes, and independent contractors.
- **31 — Manufacturing (31 portion): 80%**. Eligible workers: 5,160. Assume recurring production
  shifts predominate; allow for rotating shifts and flexible office roles.
- **32 — Manufacturing (32 portion): 80%**. Eligible workers: 12,149. Use the same manufacturing
  assumption; no evidence supports finer differentiation yet.
- **33 — Manufacturing (33 portion, including model-mapped unspecified manufacturing): 80%**.
  Eligible workers: 32,890. Use the same manufacturing assumption; model conversion also maps 3MS
  here.
- **42 — Wholesale trade: 60%**. Eligible workers: 12,599. Assume scheduled warehouse and business
  operations mixed with flexible sales and office work.
- **44 — Retail trade (44 portion): 55%**. Eligible workers: 34,326. Assume some recurring coverage
  shifts, with substantial allowance for changing weekly rosters.
- **45 — Retail trade (45 portion, including model-mapped unspecified retail): 55%**. Eligible
  workers: 15,423. Use the same retail assumption; model conversion also maps 4MS here.
- **48 — Transportation (48 portion of transportation and warehousing): 65%**. Eligible workers:
  9,296. Assume recurring routes and operating shifts, offset by irregular trips and rotating
  assignments.
- **49 — Postal services, couriers/messengers, and warehousing/storage: 75%**. Eligible workers:
  5,029. Assume recurring sorting, delivery, and warehouse shifts; allow for variable demand and
  routes.
- **51 — Information: 30%**. Eligible workers: 12,095. Assume considerable schedule discretion,
  alongside fixed operations, production, and service coverage.
- **52 — Finance and insurance: 40%**. Eligible workers: 33,808. Assume a mix of fixed
  customer-service hours and flexible professional/office schedules.
- **53 — Real estate and rental and leasing: 30%**. Eligible workers: 8,310. Assume
  appointment-driven and self-directed work is common, with fixed rental/service operations.
- **54 — Professional, scientific, and technical services: 25%**. Eligible workers: 53,441. Assume
  relatively high discretion over exact hours; retain fixed laboratory, support, and client-coverage
  roles.
- **55 — Management of companies and enterprises: 35%**. Eligible workers: 613. Assume office
  coordination but substantial discretion over exact arrival and departure times.
- **56 — Administrative/support and waste management/remediation services: 65%**. Eligible workers:
  18,462. Assume scheduled cleaning, security, support, and collection work, offset by variable
  assignments.
- **61 — Educational services: 80%**. Eligible workers: 57,894. Assume school-day and recurring
  instructional/support schedules dominate; allow flexibility in higher education and other roles.
- **62 — Health care and social assistance: 70%**. Eligible workers: 80,340. Assume recurring
  clinic, care, and service coverage; discount rotating shifts, on-call work, and variable visits.
- **71 — Arts, entertainment, and recreation: 40%**. Eligible workers: 8,470. Assume a mix of
  regular facility staffing and irregular event/performance schedules.
- **721 — Accommodation: 60%**. Eligible workers: 3,790. Assume recurring hotel/service shifts with
  allowance for changing rosters and seasonal demand.
- **722 — Food services and drinking places: 50%**. Eligible workers: 22,479. Assume recurring
  service shifts for some workers, with substantial changing weekly rosters.
- **81 — Other services, except public administration: 55%**. Eligible workers: 20,678. Assume a mix
  of fixed shop/service hours and appointment-based or self-directed work.
- **92 — Public administration: 65%**. Eligible workers: 21,982. Assume many fixed service/office
  schedules, offset by flexible office arrangements and rotating operations.

## Earlier industry-only aggregate (superseded by the logit)

Without an income effect, the proposed probabilities imply 297,980.3 expected fixed-schedule
assignments among 500,629 eligible workers, or **59.5%**. This is an expectation under the proposed
assumptions and current imputed industry mix, not a fitted regional target or a realized random
draw. Do not tune probabilities merely to retain this overall share when inputs change.

For prototype sensitivity checks, vary every probability by plus/minus 10 percentage points (bounded
by zero and one). Here that yields expected shares of 49.5% to 69.5%. These are assumption
scenarios, not confidence intervals. Also vary education and health care separately because their
large input populations give them substantial influence.

## Conversion to the industry-plus-income logit

The user has authorized a binary logit with personal income, temporarily proxied by household income
per worker. The industry probabilities above are now proposed anchors at annual income 50,000, not
unconditional industry shares. No numerical assumptions are approved or estimated yet.

Set nonfixed utility to zero and fixed utility to:

`U_fixed = log(p_industry / (1 - p_industry)) - log((1 + income / 50000) / 2)`.

This proposes an income coefficient of -1.0 and a 50,000-dollar reference/scale. Use nonnegative
income for this expression under the proposed handling in the component plan. At income 50,000 the
original probability is recovered. At 25,000 the odds of being fixed are multiplied by 4/3; at
100,000 by 2/3, relative to the reference income. These multipliers are assumptions, not estimates.

Illustrative computed probabilities:

- A 25% industry anchor becomes 30.8% at 25,000, 25.0% at 50,000, and 18.2% at 100,000.
- A 50% industry anchor becomes 57.1% at 25,000, 50.0% at 50,000, and 40.0% at 100,000.
- An 80% industry anchor becomes 84.2% at 25,000, 80.0% at 50,000, and 72.7% at 100,000.

Use industry-specific intercepts without a redundant common intercept. Their values are 0 for 50%,
0.201 for 55%, 0.405 for 60%, 0.619 for 65%, 0.847 for 70%, 1.099 for 75%, and 1.386 for 80%. The
corresponding values for 40%, 35%, 30%, and 25% are -0.405, -0.619, -0.847, and -1.099. Compute
full-precision values from the approved probabilities in implementation.

The earlier 59.5% aggregate applies only with a zero income effect. Recompute expected shares from
individual logit probabilities when the proxy and parameters are approved. For income sensitivity,
compare slopes 0, -0.5, and -1.0 as explicit prototype scenarios, not confidence bounds. See the
[component plan](fixed-work-schedule-plan.md) for denominator inconsistencies, the confirmed
person-based worker count, income provenance, and missing-data handling.

## Special codes and missing values

- **99:** 6,561 people, zero eligible workers. The donor values contributing to this bucket are 9920
  and 999920, representing an unemployment/no-recent-work category rather than a NAICS industry.
  Assign no probability. If 99 appears on an eligible worker later, report an inconsistent input
  rather than interpreting it as an industry or a zero-probability worker.
- **Blank:** 353,577 people, zero eligible workers. No fallback is needed for this input. Report any
  future missing eligible-worker industry explicitly; do not silently assign false.
- **9000:** mentioned in existing telework specifications but absent from the current person inputs.
  Do not introduce a military probability without resolving its coding separately.

## Source definitions

Industry names and combined sectors follow the
[Census NAICS sector guide](https://www.census.gov/programs-surveys/economic-census/year/2022/guidance/understanding-naics.html).
The [2022 NAICS manual](https://www.census.gov/naics/reference_files_tools/2022_NAICS_Manual.pdf)
provides the detailed structure, including transportation/warehousing and accommodation/food service
subsectors. This verifies labels; it does not establish the vintage of the model's donor coding. The
[2018 ACS PUMS documentation](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/ACS2018_PUMS_README.pdf)
explains unemployment pseudo-codes and nonstandard letter-coded NAICS equivalents.

No data, model configuration, or executable behavior has been changed. Once reviewed, approved
probabilities can be transferred to the component's configuration with assumption labels preserved.
