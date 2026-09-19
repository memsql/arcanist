# Following the Ripples: A Statistical Framework for Pinpointing the Engineering Changes That Most Reduce Support Load

| | |
| --- | --- |
| **Purpose** | Restate the premise of INFRA-5108 and specify how to measure it |
| **Primary audience** | Engineering managers and product managers who set sprint and quarter priorities |
| **Secondary audience** | The ATLAS engineering team, who build the measurement |
| **Explicitly not the audience** | The support organization, who are an *input* to this system |
| **Related** | [INFRA-5108](https://memsql.atlassian.net/browse/INFRA-5108), [ATLAS Confluence page](https://memsql.atlassian.net/wiki/spaces/CLOUDINFRA/pages/3997630469/ATLAS+Automated+Ticket+Labeling+and+Severity), [ATLAS dashboard](https://atlas.internal-virginia-1.memcompute.com/dashboard) |
| **Reproducible examples** | [`worked_example.py`](./worked_example.py), [`validation_example.py`](./validation_example.py) |

---

## 1. Executive summary

We set out to build a tool that answers one question for engineering leadership: **of everything we could change in the product we already have, which small number of changes would most reduce the cost and friction our customers experience?**

Support tickets, incidents, and customer-driven configuration changes are the ripples. Somewhere upstream there are a limited number of stones — specific defects, missing automation, bad defaults, confusing behaviors. The premise of INFRA-5108 is that if we can trace the ripples back to the stones and rank them honestly, a focused effort on the top few will produce a reduction in downstream load out of all proportion to the engineering invested.

ATLAS has built the hard plumbing for this: ingestion from Zendesk, incident.io, Jira and PagerDuty through ShareHouse, Airflow orchestration, a trained classifier, cross-system links, and a live dashboard. That plumbing is a genuine asset and nothing in this paper asks for it to be thrown away.

What is missing is the layer that turns that data into a ranked, defensible, causal answer. Concretely, five things are absent:

1. **A denominator.** We count tickets but do not divide by exposure, so we rank popular surfaces rather than broken ones.
2. **A unit of analysis that an engineer can act on.** We analyze tickets. Tickets are symptoms. We need to analyze *surfaces* — the ownable places in the product where causes live.
3. **A notion of "unusual."** Nowhere do we ask whether a surface's load is higher than we would expect. That question — how many standard deviations from the mean is this? — is the entire statistical core of the original idea, and it is not implemented.
4. **A cost weighting.** A ticket is not a unit of harm. A four-hour escalation and a one-minute question are not the same thing.
5. **A closed loop.** We have never predicted that a specific fix would remove a specific amount of load and then measured whether it did.

There is also an audience problem, which is the reason this paper exists. The natural gravity of this project has pulled it toward the support organization, because support answers quickly, has concrete requests, and is delighted by per-ticket labeling, severity prediction, SLA alerting, and a triage chatbot. Those are real and useful things. They are also a *different product* with different metrics and a different customer. The tool INFRA-5108 asked for is a **prioritization instrument for EMs and PMs**, and support's data is its sensor array, not its user base.

This paper specifies the statistics, defines the metrics, gives a worked example with real arithmetic, explains how to prove the effect of a fix after the fact, and recommends what ATLAS should keep, add, reframe, and stop.

---

## 2. The premise: the product as a black box

Treat the product as a system we cannot fully introspect. We do not need to.

**Inputs we control** — the things engineering can change:

- bug fixes
- behavior changes to existing features
- default and configuration changes
- automation and self-service that removes a manual step
- error messages, diagnostics, and observability the customer can see
- documentation and in-product guidance

**Outputs we observe** — the things the world tells us:

- Zendesk tickets and their handling cost
- incident.io incidents and PagerDuty pages
- Jira escalations and ECS requests
- configuration changes made on the customer's behalf
- repeated manual interventions by support or field engineering
- sentiment and renewal risk signals

The question is an **inverse problem**: given the outputs, infer which input changes would most improve them. This is ordinary engineering practice done at population scale. A single engineer reading a single ticket does this intuitively. The reason we need statistics is that intuition does not aggregate: nobody can hold ten thousand tickets in their head, and the ones a human remembers are the loudest, the most recent, and the ones from the customer whose name everyone knows — none of which correlate reliably with cost.

Two framing constraints, both from the original charter:

- **This is not about new features.** Product owns the question "what should we build that does not exist?" This system owns the question "what is wrong, confusing, or manual about what already exists?" Keeping that boundary sharp is what makes the tool credible to PMs rather than threatening to them.
- **We are optimizing experience and cost of the installed base**, which means the outcome variable is *load per unit of customer exposure*, not raw ticket count, and certainly not ticket count divided by headcount.

---

## 3. Why a small number of causes can dominate — and how to check rather than assume

The original writeup expressed the hope that fixing a limited number of issues produces an exponentially disproportionate reduction in tickets. The intuition is sound and worth stating precisely, because the precise version is testable and the loose version is not.

Empirically, defect and support load tends to be **heavily concentrated**: a small fraction of causes accounts for a large fraction of load. When a distribution is concentrated in this way, two things follow:

- Fixing the top-ranked cause returns far more than fixing the fifth-ranked one. In the worked example in §9, the top item is worth nearly six times the third and twenty times the fourth. Marginal return decays steeply.
- Therefore **accuracy at the very top of the ranking matters more than breadth of coverage**. A system that surfaces four hundred insights is worse than one that surfaces the correct three.

There is a second, compounding effect that justifies part of the "exponential" intuition. Removing a recurring cause does not remove one ticket; it removes a *stream*. It also removes the escalations that stream generates, the incident reviews, the context-switching for the on-call engineer, and the support capacity consumed — which in turn shortens queues for everything else. The first-order saving is measurable directly. The second-order saving is real but harder to attribute, and we should claim it qualitatively rather than put a number on it we cannot defend.

**Do not assume the concentration; measure it.** Before the program promises leverage, run the diagnostic:

1. Attribute load to surfaces (§5) and cost-weight it (§7).
2. Sort surfaces by weighted load, descending.
3. Plot the cumulative share — a Lorenz curve — and compute the top-k share and the Gini coefficient.

If the top 10 surfaces account for a large share of recoverable load, the thesis holds and the tool has a job. If the curve is nearly flat, the honest finding is that load is diffuse, there is no small set of high-leverage fixes, and leadership should be told that rather than handed a fabricated top ten. Publishing this diagnostic first, before any recommendations, is what earns the rest of the analysis its credibility.

---

## 4. What we must measure: four ledgers

Everything in this framework is built from four tables. ATLAS today has most of the first and part of the fourth.

| Ledger | Contents | Status today |
| --- | --- | --- |
| **Event ledger** | Every ticket, incident, page, escalation, and customer-driven config change, timestamped, with customer, product area, and handling cost | Largely built via ShareHouse ingestion |
| **Surface ledger** | The canonical list of causal surfaces (§5), each with an owning EM, a PM, and a mapping to code or configuration | **Missing** |
| **Exposure ledger** | For each surface and time window, how much opportunity there was for an event to occur: customers using the feature, workspace-months, workload volume, upgrade attempts | **Missing** |
| **Change ledger** | Every release, deploy, feature flag flip, default change, and merged fix, timestamped, mapped to surfaces, with rollout cohorts | Partially available from Jira and release data; not joined to the others |

The exposure ledger is the single highest-value missing piece and the one most likely to be skipped because it is unglamorous. Without it, every number in the system is a popularity contest. The change ledger is the second, because without it we can observe that something is bad but never learn what made it bad or prove that we fixed it.

---

## 5. The unit of analysis: causal surfaces, not tickets

A **surface** is the smallest locus of causation that a single engineering team can own and change. Examples: `backup/restore`, `upgrade path 8.5 → 8.7`, `connection pooling token expiry`, `autoscale threshold defaults`, `documentation for a specific SQL function family`, `region failover runbook`.

A surface is not a product ("SingleStore Helios"), not a support category ("Performance"), and not a ticket. Support categories are organized around *who answers*; surfaces are organized around *who fixes*. That difference is the whole reason the existing taxonomy cannot be reused unchanged.

Rules that make the surface ledger usable:

- **Every surface has a named EM and a named PM.** A surface nobody owns cannot be prioritized, and an unowned top-ten entry is how a report dies.
- **Surfaces are stable across quarters.** Rankings are only meaningful as time series if the categories do not churn.
- **Events map to one or more surfaces with weights that sum to one.** A ticket that is 70% upgrade path and 30% documentation should say so rather than being forced into a single bucket.
- **The classifier proposes; humans audit.** This is where the CatBoost model and the embedding/clustering work already built become genuinely valuable — not as an end product but as the labeling substrate. Audit a random sample of attributions every cycle and publish the measured accuracy alongside the rankings. A ranking whose input labels are 60% accurate is not a ranking.
- **Clustering discovers candidate surfaces; it does not define them.** Unsupervised clusters are excellent at revealing a recurring problem nobody had named. Once named and given an owner, it becomes a surface and stops being a cluster.

This reframing is the single most important change in this paper. Statistics computed over tickets tell you what customers talk about. Statistics computed over surfaces tell you what to change. They are not the same question and they frequently have different answers.

---

## 6. Normalizing: rate, not count

Raw counts rank surfaces by how many customers touch them. What we want is how *badly* each surface behaves when touched.

```
rate_s = events_s / exposure_s
```

Exposure is whatever unit best represents "opportunity for something to go wrong" for that surface:

| Surface type | Sensible exposure denominator |
| --- | --- |
| Always-on runtime behavior | workspace-months, cluster-hours |
| Upgrade path | number of upgrade attempts |
| Feature-specific | customers with that feature enabled, or invocations |
| Onboarding or setup | new workspaces created |
| Operational runbook | number of times the procedure ran |

Choosing the denominator is a modeling decision, and it must be recorded next to the number. A rate whose denominator is unstated is not interpretable.

Why this matters concretely: a surface used by every customer will always top a raw-count list even if it is working well, and a badly broken surface used by fifty customers will never appear. §9 shows this happening with real arithmetic — the raw-count top three and the rate top three overlap in only one entry, and it sits in a different position in each.

**Watch for Simpson's paradox.** A surface can look fine in aggregate while being severe for one customer tier, one region, or one version. Always compute rates stratified by the dimensions that plausibly matter — version, tier, cloud, deployment mode — and treat "bad only in one stratum" as a finding rather than noise. It is often the most actionable kind of finding, because the stratum names the cause.

---

## 7. Pricing the output: cost-weighted load

An event's cost is not one. Assign each event a cost in fully loaded hours:

```
cost = support_handling_hours
     + escalation_engineering_hours
     + incident_response_hours x severity_weight
     + customer_impact_weight
```

Sources: Zendesk time tracking, Jira worklogs, incident.io severity and duration, and an agreed weight for customer-facing impact. The weights should be set once, jointly, by the EM group and support leadership, and then left alone — renegotiating weights per cycle is how ranking systems get gamed.

Two cautions:

- **Cost distributions are heavy-tailed.** A handful of events consume enormous effort. Report both the median-based and mean-based weighted load; if they disagree sharply, the surface's problem is tail risk rather than volume, which implies a different fix.
- **Do not put sentiment in the cost function as a headline term.** Sentiment scores are noisy, culturally variable, and easily gamed. Sentiment is useful as a tiebreaker and as evidence when presenting a case, not as a ranking key. This is a deliberate demotion of an item in the original scope.

---

## 8. Finding the outliers: "standard deviations from the mean," done properly

This section is the statistical core. It is written for readers without formal statistics training, and each step exists because the previous step has a specific, known failure mode.

### 8.1 Expectation

If a surface behaved exactly like the average surface, how many events would it produce?

```
expected_s = exposure_s x m        where m = total_events / total_exposure
```

`m` is the population rate. `expected_s` is the null hypothesis: nothing special here.

### 8.2 Excess and the naive z-score

```
excess_s = observed_s - expected_s
z_s      = excess_s / sqrt(expected_s)
```

This is literally "how many standard deviations above the mean is this surface." The square root comes from the Poisson distribution, the standard model for counting independent events: for a Poisson count, the variance equals the mean, so the standard deviation is the square root of the expected count.

A z of +2 means "unusual." A z of +5 means "this did not happen by chance." Ranking by z rather than by count is already a large improvement over anything ATLAS does today.

But taken alone it is wrong, in two directions, and both errors are severe.

### 8.3 Over-dispersion: real ticket data is burstier than Poisson

Poisson assumes events are independent. Support events are emphatically not. One frustrated customer files nine tickets about one problem in one afternoon. One incident spawns a cluster of correlated reports. The real variance is far larger than the mean — in the worked example, roughly 150 times larger at median exposure.

Ignoring this inflates every z-score enormously and makes high-volume surfaces look overwhelmingly significant. In §9 the naive Poisson z for the busiest surface is +19, which would ordinarily mean "certainty." The honest value is +1.45, which means "mildly interesting."

The fix is the **negative binomial** model, which adds a between-surface variance term `v`:

```
var_s = expected_s + exposure_s^2 x v
z_s   = (observed_s - expected_s) / sqrt(var_s)
```

`v` is estimated from the spread of observed rates across surfaces, after subtracting the portion attributable to counting noise. Two practical alternatives that achieve the same end: aggregate events to the customer-surface level before counting, so one customer's burst counts once; or fit the model with cluster-robust standard errors grouped by customer. Doing at least one of these is not optional. It is the difference between a system that flags twenty surfaces as critical every week and one whose alerts mean something.

### 8.4 Shrinkage: the small-sample trap

The opposite error. A surface with 900 workspace-months of exposure and 7 events has a rate more than double the population average — but with 7 events, we know almost nothing. Rank by raw rate and the top of the list fills with thin-exposure surfaces whose apparent severity is noise. Next cycle they will be replaced by a different set of thin surfaces, and the report will look arbitrary to the EMs reading it. Nothing destroys confidence in a prioritization tool faster than a top ten that reshuffles every month for no visible reason.

The remedy is **empirical Bayes shrinkage**. Fit a Gamma prior to the population of rates and report the posterior mean:

```
shrunk_rate_s = (observed_s + alpha) / (exposure_s + beta)
```

where `alpha` and `beta` come from the same population fit that produced `v`. The effect is intuitive: a surface with plenty of exposure keeps essentially its observed rate; a surface with little exposure is pulled toward the population mean in proportion to our ignorance. In §9, the highest-exposure surfaces move by about 1%, while the thinnest moves by 25%.

Shrinkage is also what makes rankings stable over time, which is what makes them trustworthy.

A useful companion visual is the **funnel plot**: rate on the vertical axis, exposure on the horizontal, with control limits that flare out at low exposure. Surfaces outside the funnel are genuinely unusual; the crowd of noisy small surfaces sits visibly inside it. It is the single most effective chart for explaining this trap to a non-statistical audience, and it belongs on the dashboard.

### 8.5 Many surfaces, many chances to be fooled

Testing 300 surfaces at a 5% threshold yields roughly 15 false alarms even if nothing is wrong anywhere. Apply a false discovery rate correction — Benjamini–Hochberg is sufficient and simple — and report the corrected values. Without it, "we found 15 anomalies" means nothing.

### 8.6 Time: is it new, is it growing, when did it start?

A surface that has been mediocre for two years is a different decision from one that doubled last month. Three tools, each answering a different question:

- **Control charts (u-chart)** on the rate per unit exposure, with limits at ±3 standard deviations, adjusted for over-dispersion. Answers: *is this out of control right now?*
- **EWMA and CUSUM.** Exponentially weighted moving average catches gradual drift; cumulative sum catches small persistent shifts that a 3-sigma rule never trips. Most real regressions are small and persistent, not dramatic. This is where CUSUM earns its place.
- **Change-point detection** on the weekly series. Answers: *when did this start?* — which is the question that hands you the suspect, because you can then look up which releases, flag flips, or config defaults landed in that window from the change ledger.

Classify each surface into one of three regimes, because they demand different responses:

| Regime | Signature | Response |
| --- | --- | --- |
| **Chronic** | Steady, elevated, no trend | Roadmap item. Highest total value, lowest urgency. |
| **Acute** | Sharp change point | Find the change that caused it; often a revert or a targeted fix. |
| **Emergent** | Accelerating, low absolute volume | Watch and get ahead of it before it becomes chronic. |

Today ATLAS alerts on SLA breaches, which is a support operations concern. The alerting that serves this program is regime change on a surface, routed to the owning EM.

### 8.7 Recurrence: the same customer, the same problem, again

Counting events treats ten tickets from ten customers the same as ten tickets from one customer. For prioritization these are completely different: the second is a persistent unfixed defect experienced by someone losing patience.

Track, per surface, the **mean cumulative function** — the average number of repeat events per affected customer over time — and the distribution of inter-arrival times. High recurrence is the strongest available signal that a *durable* cause exists and has not been addressed, as opposed to a set of one-off user errors. Recurrence deserves an explicit multiplier in the value model, and it maps directly to the "reduction in repeat incidents" success metric already in the charter.

---

## 9. Worked example

Ten surfaces over a 90-day window. The numbers are illustrative but the arithmetic is real and reproducible with [`worked_example.py`](./worked_example.py). Exposure is workspace-months; rates are per 1,000.

Population rate: 3.17 events per 1,000 workspace-months. Between-surface variance implies roughly 150x Poisson dispersion at median exposure.

### Counts, rates, and the two z-scores

| Surface | Events | Exposure | Rate/1k | Expected | z (Poisson) | z (NB) |
|---|---|---|---|---|---|---|
| Ingest pipeline error handling | 412 | 52,000 | 7.92 | 165.0 | +19.2 | +1.45 |
| Docs: SQL function semantics | 205 | 50,000 | 4.10 | 158.7 | +3.7 | +0.28 |
| Backup / restore | 143 | 48,000 | 2.98 | 152.3 | -0.8 | -0.06 |
| Upgrade path 8.5 -> 8.7 | 96 | 6,000 | 16.00 | 19.0 | +17.6 | +3.82 |
| Connection pooling / token expiry | 88 | 51,000 | 1.73 | 161.8 | -5.8 | -0.44 |
| Autoscale thresholds | 64 | 44,000 | 1.45 | 139.6 | -6.4 | -0.52 |
| Workspace resize | 31 | 1,200 | 25.83 | 3.8 | +13.9 | +6.20 |
| Billing / usage reporting | 27 | 53,000 | 0.51 | 168.2 | -10.9 | -0.81 |
| Pipeline monitoring UI | 19 | 38,000 | 0.50 | 120.6 | -9.3 | -0.81 |
| Region failover runbook | 7 | 900 | 7.78 | 2.9 | +2.5 | +1.22 |

Note what the correction for over-dispersion does. Under Poisson, eight of the ten surfaces clear the conventional |z| > 3 bar, several of them absurdly. Under the honest model, two do. Note also the negative rows: those surfaces are *better* than average and are not candidates for investment at all — a fact invisible on a raw-count dashboard, where "Backup / restore" appears third from the top.

### Shrinkage, excess load, and value

Annualized hours assume the excess persists and that a fix removes the stated fraction of it. Effort is the owning EM's own estimate, in whatever unit the team uses consistently.

| Surface | Rate/1k | Shrunk/1k | Pull | Excess events | Excess hrs | Annualized hrs | Effort | Hrs per effort |
|---|---|---|---|---|---|---|---|---|
| Upgrade path 8.5 -> 8.7 | 16.00 | 15.40 | 5% | +73 | +719 | +2478 | 5 | **+496** |
| Ingest pipeline error handling | 7.92 | 7.90 | 1% | +246 | +761 | +2161 | 8 | **+270** |
| Workspace resize | 25.83 | 21.35 | 20% | +22 | +159 | +420 | 3 | **+140** |
| Docs: SQL function semantics | 4.10 | 4.09 | 1% | +46 | +55 | +123 | 2 | +62 |
| Region failover runbook | 7.78 | 6.64 | 25% | +3 | +44 | +124 | 6 | +21 |
| Backup / restore | 2.98 | 2.98 | 1% | -9 | -59 | — | 10 | — |
| Connection pooling / token expiry | 1.73 | 1.73 | 1% | -73 | -308 | — | 4 | — |
| Autoscale thresholds | 1.45 | 1.47 | 1% | -75 | -383 | — | 6 | — |
| Billing / usage reporting | 0.51 | 0.52 | 1% | -140 | -281 | — | 3 | — |
| Pipeline monitoring UI | 0.50 | 0.52 | 1% | -101 | -161 | — | 2 | — |

### The punchline: every correction changes the answer

| Ranked by | 1st | 2nd | 3rd |
|---|---|---|---|
| Raw count | Ingest pipeline | Docs: SQL semantics | Backup / restore |
| Raw rate | Workspace resize | Upgrade path | Ingest pipeline |
| z (Poisson) | Ingest pipeline | Upgrade path | Workspace resize |
| z (negative binomial) | Workspace resize | Upgrade path | Ingest pipeline |
| Annualized hours recoverable | **Upgrade path** | **Ingest pipeline** | **Workspace resize** |
| Hours recoverable per unit effort | **Upgrade path** | **Ingest pipeline** | **Workspace resize** |

The raw-count ranking — which is what a conventional support dashboard shows — gets the top three wrong, and its second and third entries (a documentation issue worth 5% of the leader, and a surface that is performing *better* than average) would waste a quarter.

Concentration of recoverable load across the five positive surfaces: the top one holds 47%, the top two hold 87%, the top three hold 95%. Gini 0.75. In this dataset the leverage thesis holds decisively, and that is the claim to put in front of leadership — with the curve, not as an assertion.

---

## 10. From outlier to cause: attribution and natural experiments

An outlier tells us *where*. Prioritization needs *why*, because the fix has to be specific. Four techniques, in increasing order of strength.

**Co-occurrence and association.** Within a surface, mine the events for shared attributes: version, cloud, region, workload shape, config values, error signatures. A surface whose excess load is 80% concentrated in one version has effectively named its own cause. This is cheap, uses data already ingested, and should be the default drill-down on every dashboard entry.

**Change-point alignment.** Line up the surface's change points against the change ledger. If the rate tripled in the week a default changed, that default is the leading suspect. Weak on its own — many things ship every week — but powerful in combination with the next two.

**Interrupted time series.** Model the surface's weekly rate with terms for pre-existing level, pre-existing trend, a step at the change, and a slope change after it. This distinguishes "the change made it worse" from "it was already getting worse." That distinction is frequently the difference between a correct and an incorrect roadmap decision.

**Difference-in-differences on staged rollouts.** This is the strongest tool available to us and we get it for free. Every time a version, a flag, or a default reaches some customers before others, we have created a natural experiment: a treated cohort and a control cohort. Comparing the *change* in the treated cohort against the *change* in the control cohort removes everything that affected both — seasonality, install-base growth, a support process change, a marketing push.

Making this usable requires one thing: **the rollout cohort must be recorded in the change ledger at rollout time.** Reconstructing who had what and when, months later, is painful and often impossible. This is a small, cheap engineering requirement with disproportionate analytical value, and it should be prioritized ahead of any further dashboard work.

Throughout, keep the epistemics honest: label each attribution as *observed correlation*, *natural experiment*, or *confirmed by fix*, and show the label in the report. EMs will forgive uncertainty that is declared. They will not forgive a confident claim that turns out to be an artifact.

---

## 11. From cause to priority: the value model

For each candidate intervention — a fix, a behavior change, a new default, a piece of automation, a documentation change — compute:

```
addressable_load = sum over surfaces of (attributable excess hours x attribution confidence)
annual_value     = addressable_load x fix_effectiveness x persistence x (365/window_days)
score            = annual_value / effort
```

Four disciplines make the difference between a model that is trusted and one that is ignored:

1. **Carry uncertainty all the way through.** The negative binomial fit gives a posterior interval on excess load; propagate it. Rank on a conservative quantile — the 25th percentile of the value distribution — rather than the point estimate. This systematically prefers well-evidenced medium wins over speculative large ones, which is the correct bias for a system that has to earn trust.
2. **`fix_effectiveness` is an estimate, so calibrate it.** Start at a default and update it from measured outcomes (§12). Teams are optimistic about their fixes; the data will say by how much, and after a few cycles the model will know.
3. **Publish a short list.** Ten items with owners, confidence intervals, and predicted savings. Not four hundred insights. The whole value proposition is *pinpointing*, and a long list is a failure to do the job.
4. **State a falsifiable prediction per item.** "Fixing the 8.5→8.7 upgrade path should reduce upgrade-attributed events by 40–60% for upgrading customers within one quarter of the fix reaching them." This is what makes the next section possible, and it is what converts the tool from an opinion generator into an instrument.

---

## 12. Closing the loop: proving that it worked

A prioritization system that never checks itself decays into an expensive opinion. The loop is: predict, ship, measure, calibrate.

The naive measurement — compare the ticket rate before and after — is badly biased, because everything else moved too. Use difference-in-differences against a cohort that has not received the fix. Worked example, reproducible with [`validation_example.py`](./validation_example.py):

| | Before | After | Change |
|---|---|---|---|
| Treated cohort (fix shipped) | 33.12 | 12.22 | −63% |
| Control cohort (not yet) | 24.46 | 17.98 | −26% |

The naive read is a 63% reduction. But the control cohort improved 26% without the fix, so a meaningful part of the treated cohort's improvement would have happened regardless. The difference-in-differences estimate is a **50% reduction (95% CI: 16% to 70%)**, allowing for over-dispersion. Events avoided in the treated cohort during the window: 120 against a counterfactual of 241.

Two lessons, both important to internalize before the first result is presented:

- **The naive number overstated the win by 13 points.** Reporting it would have inflated the program's credit and, worse, mis-calibrated the effectiveness estimate for every future recommendation.
- **The confidence interval is wide.** With realistic volumes and realistic burstiness, we can say "this clearly helped, probably by about half," not "this helped by exactly 50%." Report the interval. A program that reports intervals survives its first miss; a program that reports point estimates does not.

Everything predicted goes into an **impact ledger**: prediction, what shipped, measured effect, confidence interval, hours avoided, cumulative running total. This ledger is the artifact that justifies the program's continued existence and, not incidentally, is the most effective answer to the "low buy-in" risk already identified in INFRA-5108. Buy-in follows demonstrated savings; it does not follow dashboards.

**Pre-register.** Record the prediction, the metric, the cohorts, and the measurement window *before* the work starts. Choosing the analysis after seeing the outcome guarantees a flattering result and worthless information.

---

## 13. Who this tool is for

This section exists because the project has drifted, and the drift is structural rather than anyone's mistake.

**Support is an instrument, not the customer.** The support organization operates the sensor array. Their data is the input; their domain expertise is essential for validating attributions; their taxonomy questions are legitimate. What they are not is the audience for the output. The output is a prioritization decision, and prioritization decisions are made by EMs and PMs.

Why the drift happens, predictably, to any project of this type: support is present, responsive, and specific. Ask a support lead what they want and you get an answer today — better ticket labels, faster triage, severity prediction, an assistant that drafts replies. Ask an EM and you get a slow, vague answer, because the thing they need does not exist yet and is hard to imagine. So the team builds for the feedback loop that is available rather than the one that matters. Every telemetry-and-insights project faces this. The remedy is not willpower; it is deliberately instrumenting the intended audience — a standing slot in quarterly planning, a named EM sponsor per report, and a metric that only moves when an EM acts.

The distinction in concrete terms:

| | Support operations tool | Engineering prioritization instrument |
| --- | --- | --- |
| **Primary user** | Support agents and leads | EMs and PMs |
| **Unit of analysis** | The individual ticket | The surface, across all tickets |
| **Time horizon** | Minutes to hours | Quarter to year |
| **Headline metric** | Time to triage, SLA attainment | Load per unit exposure; validated hours avoided |
| **Decision it drives** | How to route and answer this ticket | What to build or fix next quarter |
| **Statistical core** | Per-item classification accuracy | Population-level excess and causal attribution |
| **Failure mode** | Slow or misrouted tickets | A confident ranking that is wrong |
| **Value realized when** | A ticket is handled faster | A ticket never gets filed |

Both are worth having. Conflating them is what produces a tool that serves neither, because the second one's value shows up as *tickets that never existed* — which is invisible on any dashboard built for the first.

**Operating model.**

| Role | Responsibility |
| --- | --- |
| Support | Provides event data and cost data; validates a sample of attributions; consumes the operational tooling as a separate product |
| ATLAS team | Owns the ledgers, the statistics, the attribution, and the report |
| EMs | Own surfaces; receive the ranked list; commit or decline with a recorded reason; supply effort estimates |
| PMs | Adjudicate between fixing existing behavior and building new capability; own the customer-impact weights |
| Exec sponsor | Reviews the impact ledger; protects the boundary between this and support tooling |

The **decline-with-a-reason** step matters more than it looks. It is the only mechanism that tells us whether the tool is producing recommendations that are wrong, unownable, or merely unwelcome — three problems with three different fixes.

---

## 14. What this means for ATLAS as built

The existing system is a real asset. This is a redirection of the analytical layer, not a rebuild.

**Keep, unchanged:** ShareHouse ingestion from Zendesk, incident.io, Jira and PagerDuty; Airflow orchestration; the CatBoost classifier as the labeling substrate; embeddings and clustering as a *discovery* mechanism for unnamed surfaces; cross-system Zendesk-to-Jira links (these are the beginning of the change ledger and more valuable than they currently look); the dashboard shell and deployment.

**Add — in dependency order, because each step is useless without the previous one:**

1. **The surface ledger** with EM and PM ownership. Nothing else works without it.
2. **The exposure ledger**, starting with whatever denominators are obtainable today. An imperfect denominator beats none decisively.
3. **The cost model**, using Zendesk time tracking and Jira worklogs.
4. **The statistical layer**: population fit, negative binomial excess, empirical Bayes shrinkage, FDR correction, funnel plots, control charts, change-point detection, recurrence curves. This is a modest amount of code — the reference implementations in this directory are under 200 lines each and have no dependencies.
5. **Rollout cohort capture** in the change ledger, which unlocks difference-in-differences.
6. **The quarterly ranked report** and the impact ledger.

**Reframe:** per-ticket severity prediction, SLA breach alerting, the Ask ATLAS assistant, and the Zendesk classification dashboards are support operations products. They appear to be useful and should continue — under a separate name, a separate metric, and a separate backlog, so they stop competing for the causal-analysis roadmap. Note that two recent tickets already move in the right direction: INFRA-6029 explicitly targets EM and PM prioritization decisions, and INFRA-6057 removed SLA-derived fields from ATLAS-facing views in favor of source-backed facts. The course correction has begun; this paper is asking for it to be completed and made explicit.

**Demote:** sentiment analysis, from a headline capability to a cost-model input and presentation aid (§7).

**Reinstate:** INFRA-5214 (guardrails) and INFRA-5215 (monitoring and observability) were rejected. A system whose output steers engineering investment needs model monitoring, attribution-accuracy tracking, and drift detection. Without them we cannot answer "is the ranking still trustworthy?", and the honest answer at that point is "we don't know."

---

## 15. Phases and exit criteria

Phases are defined by exit criteria rather than duration, so progress is verifiable rather than asserted. Each phase is independently useful; stopping after any one of them leaves something better than nothing.

| Phase | Goal | Exit criteria |
| --- | --- | --- |
| **0. Instrumentation** | The four ledgers exist and join | Every event in the window maps to at least one surface; every surface has an owner and a denominator; audited attribution accuracy is published |
| **1. Concentration diagnostic** | Test the leverage premise | Lorenz curve and Gini of cost-weighted load published; top-k share stated; explicit verdict on whether concentration is sufficient to justify the program |
| **2. Excess ranking** | Produce the first honest top ten | Negative binomial excess with shrinkage and FDR control, ranked by value per effort, with intervals; reviewed by the named EMs |
| **3. Causal attribution** | Explain the top ten | Each entry carries a named suspected cause and an evidence grade; rollout cohorts captured going forward |
| **4. Closed loop** | Prove the effect | At least three pre-registered predictions measured by difference-in-differences; impact ledger live; `fix_effectiveness` recalibrated from outcomes |

---

## 16. Success metrics, revised

The metrics in the original charter measure activity. These measure whether the premise is true and whether we are acting on it.

| Original | Problem | Replacement |
| --- | --- | --- |
| MTTR reduction of 30% | Measures support efficiency, not engineering focus. Can improve while the product gets worse. | Reduction in cost-weighted load per unit exposure for surfaces we acted on, measured by difference-in-differences |
| 50% more engineering time on top-priority categories | Measures input, not outcome. Trivially satisfiable by relabeling. | Share of surface-attributable engineering effort directed at top-decile surfaces, with the decile defined before the quarter starts |
| Reduction in repeat incidents | Directionally right, undefined | Mean cumulative function per affected customer, per surface, tracked quarter over quarter |
| Adoption of AI insights in planning | Unmeasurable | Number of ranked recommendations accepted or explicitly declined with a recorded reason; acceptance rate as a quality signal |
| — | — | **Validated hours avoided, cumulative** — the headline number for the exec sponsor |
| — | — | **Rank stability**: overlap between consecutive quarters' top tens. Very low overlap means the model is noisy; very high means it is stale or nobody is acting |
| — | — | **Attribution accuracy** from the human audit sample, published with every report |

---

## 17. Risks and how this fails

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| No exposure data | Rankings become popularity contests | Ship approximate denominators early; state them explicitly |
| Over-dispersion ignored | Everything looks significant; alerts become noise | Negative binomial or customer-level aggregation, mandatory |
| Small-sample noise at the top | Rankings churn; EMs stop reading | Empirical Bayes shrinkage; funnel plots |
| Confounding by growth | Growing features look broken | Rate normalization plus difference-in-differences with controls |
| Reporting bias | Loud customers dominate; silent pain is invisible | Weight by exposure; cross-check against telemetry, not just tickets |
| Misattribution by the classifier | Confidently wrong rankings | Audited sample every cycle; publish accuracy; propagate attribution confidence into the score |
| Multiple comparisons | Spurious "findings" every week | FDR correction |
| Goodhart's law | Categories get gamed once they drive investment | Stable surface definitions; audit; owners cannot reclassify their own surfaces |
| Drift back to support tooling | The original purpose is lost again | Separate backlog, separate metrics, named EM sponsor, standing planning slot |
| Concentration turns out to be weak | The leverage premise fails | Phase 1 tests it explicitly and reports the honest answer before recommendations are made |

The last row deserves emphasis. The value of running the concentration diagnostic first is that it is a real test the program can fail. A measurement system that cannot return an unwelcome answer is not measuring anything.

---

## Appendix A: formula reference

```
Population rate            m = sum(events) / sum(exposure)
Expected                   E_s = exposure_s * m
Excess                     X_s = observed_s - E_s
Poisson z                  z_s = X_s / sqrt(E_s)
Negative binomial variance var_s = E_s + exposure_s^2 * v
Negative binomial z        z_s = X_s / sqrt(var_s)
Gamma prior (MoM)          alpha = m^2 / v,  beta = m / v
Shrunk rate                lambda_s = (observed_s + alpha) / (exposure_s + beta)
Cost-weighted load         W_s = sum over events of cost
Difference-in-differences  log RR = [log(r_treat_post) - log(r_treat_pre)]
                                  - [log(r_ctrl_post)  - log(r_ctrl_pre)]
DiD standard error         SE = sqrt(phi * (1/O_tp + 1/O_tr + 1/O_cp + 1/O_cr))
Annual value               V_i = addressable_hours * effectiveness * persistence * 365/window
Priority score             S_i = V_i / effort_i     (rank on the 25th percentile of V_i)
```

`v` is the between-surface variance of the rate, estimated as the exposure-weighted variance of observed rates minus the exposure-weighted mean sampling variance. `phi` is the over-dispersion factor from the residual deviance of the weekly counts.

## Appendix B: minimum data contract

| Field | Why it is required |
| --- | --- |
| Event ID, source system, timestamp | Deduplication and time series |
| Customer ID, tier, region, deployment mode | Stratification and cluster-robust variance |
| Product version at time of event | Version-cohort attribution |
| Surface attribution with weights and confidence | Unit of analysis |
| Handling hours (support, engineering, incident) | Cost weighting |
| Severity and customer-facing duration | Cost weighting |
| Resolution category and linked Jira issue | Closing the loop from cause to fix |
| Exposure by surface and period | The denominator |
| Change events with timestamp, surface, and **rollout cohort** | Attribution and difference-in-differences |

## Appendix C: glossary

- **Mean / standard deviation** — the average, and the typical distance from it. "Two standard deviations above the mean" means unusually high relative to normal variation.
- **Poisson** — the standard model for counting independent random events. Its variance equals its mean, which is why the standard deviation of a count is the square root of its expected value.
- **Over-dispersion** — real data varying more than the model predicts, usually because events arrive in correlated bursts. Ignoring it makes everything look significant.
- **Negative binomial** — a count model with an extra variance parameter, appropriate for bursty data like support tickets.
- **Empirical Bayes / shrinkage** — pulling estimates from small samples toward the population average, in proportion to how little data supports them. Prevents thin categories from dominating rankings by luck.
- **Funnel plot** — rate against sample size with flaring control limits; makes the small-sample trap visible at a glance.
- **Control chart / CUSUM / EWMA** — process-monitoring tools that detect, respectively, sudden excursions, small persistent shifts, and gradual drift.
- **Change-point detection** — locating when a time series changed behavior.
- **Interrupted time series** — modeling level and trend before and after a known change to estimate its effect.
- **Difference-in-differences** — comparing the change in a treated group against the change in an untreated group, which cancels out everything that affected both.
- **False discovery rate** — the expected proportion of false alarms among flagged results; controlled with Benjamini–Hochberg when testing many categories at once.
- **Lorenz curve / Gini** — measures of how concentrated a distribution is. Gini 0 means perfectly even; 1 means one category holds everything.
- **Mean cumulative function** — the average number of repeat events per affected subject over time; the standard tool for recurring-event data.
- **Simpson's paradox** — an aggregate that reverses direction once the data is split by a relevant subgroup.
- **Goodhart's law** — when a measure becomes a target, it stops being a good measure.

## Appendix D: the report template

One page, quarterly, to EMs and PMs:

1. **Verdict on concentration** — Lorenz curve, top-10 share. Is there leverage this quarter?
2. **The top ten**, each with: surface, owner, excess load with interval, annualized hours recoverable, suspected cause, evidence grade, effort estimate, score.
3. **Regime changes** — surfaces that newly went out of control, with the change-point date and the candidate changes from that window.
4. **Impact ledger** — predictions made previously, measured outcomes, cumulative validated hours avoided, and current calibration of `fix_effectiveness`.
5. **Health of the instrument** — attribution accuracy from the audit sample, coverage, rank stability against last quarter.

Nothing else. If a section cannot fit, it belongs in a drill-down, not on the page. The product of this program is a decision, and a decision that takes twenty pages to support is not being supported.
