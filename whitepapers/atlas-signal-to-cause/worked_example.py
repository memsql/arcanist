#!/usr/bin/env python3
"""Reproduces the worked example in signal-to-cause-whitepaper.md.

Pure standard library so it runs anywhere, including inside a DAG task.
The dataset is illustrative and deterministic; swap `SURFACES` for a query
against the real surface ledger to get live numbers.

Usage:
    python3 worked_example.py
"""

import math
from dataclasses import dataclass


@dataclass
class Surface:
    name: str
    tickets: int  # events attributed to this surface in the window
    exposure: float  # denominator: workspace-months of customers exposed to it
    cost_per_event: float  # fully loaded hours per event (support + eng + incident)
    fix_effectiveness: float  # p(a shipped fix removes an attributed event)
    effort: float  # engineering effort units, supplied by the owning EM


# 90-day window. Numbers are illustrative, chosen to make the ranking
# pathologies visible; they are not measurements.
SURFACES = [
    #          name                              tickets exposure  cost  eff  effort
    Surface("Ingest pipeline error handling",       412,  52_000,  3.1, 0.70,  8.0),
    Surface("Docs: SQL function semantics",         205,  50_000,  1.2, 0.55,  2.0),
    Surface("Backup / restore",                     143,  48_000,  6.4, 0.60, 10.0),
    Surface("Upgrade path 8.5 -> 8.7",               96,   6_000,  9.8, 0.85,  5.0),
    Surface("Connection pooling / token expiry",     88,  51_000,  4.2, 0.75,  4.0),
    Surface("Autoscale thresholds",                  64,  44_000,  5.1, 0.50,  6.0),
    Surface("Workspace resize",                      31,   1_200,  7.3, 0.65,  3.0),
    Surface("Billing / usage reporting",             27,  53_000,  2.0, 0.80,  3.0),
    Surface("Pipeline monitoring UI",                19,  38_000,  1.6, 0.60,  2.0),
    Surface("Region failover runbook",                7,     900, 14.0, 0.70,  6.0),
]

PER_1K = 1_000.0  # rates are quoted per 1,000 workspace-months


def fit_prior(surfaces):
    """Method-of-moments Gamma prior for the per-surface event rate.

    Model: O_s ~ Poisson(lambda_s * E_s), lambda_s ~ Gamma(alpha, beta).
    Marginally O_s is negative binomial with
        mean = E_s * m
        var  = E_s * m + E_s^2 * v
    where m is the population mean rate and v its between-surface variance.
    That single fit gives us both the over-dispersed z-score and the
    shrunk rate estimate, so the two never disagree.
    """
    total_events = sum(s.tickets for s in surfaces)
    total_exposure = sum(s.exposure for s in surfaces)
    m = total_events / total_exposure

    # Exposure-weighted variance of the observed rates, minus the part that is
    # just Poisson sampling noise. What is left is real between-surface spread.
    w_total = total_exposure
    raw_var = sum(s.exposure * (s.tickets / s.exposure - m) ** 2 for s in surfaces) / w_total
    sampling_var = sum(s.exposure * (m / s.exposure) for s in surfaces) / w_total
    v = max(raw_var - sampling_var, m * m * 1e-6)

    alpha = m * m / v
    beta = m / v
    return m, v, alpha, beta


def gini(values):
    """Gini coefficient of a load distribution. 0 = flat, 1 = one surface owns it all."""
    xs = sorted(values)
    n = len(xs)
    total = sum(xs)
    if total == 0:
        return 0.0
    cumulative = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cumulative) / (n * total) - (n + 1) / n


def analyze(surfaces):
    m, v, alpha, beta = fit_prior(surfaces)
    rows = []
    for s in surfaces:
        expected = s.exposure * m
        raw_rate = s.tickets / s.exposure * PER_1K

        # "Standard deviations from the mean", the naive way: assumes the only
        # noise is Poisson counting noise.
        z_poisson = (s.tickets - expected) / math.sqrt(expected)

        # The same idea, honest about over-dispersion. Tickets arrive in bursts
        # from the same customer, so the variance exceeds the mean.
        z_nb = (s.tickets - expected) / math.sqrt(expected + s.exposure**2 * v)

        # Empirical-Bayes posterior rate: pulls thin-exposure surfaces back
        # toward the population mean in proportion to how little we know.
        shrunk_rate = (s.tickets + alpha) / (s.exposure + beta) * PER_1K
        shrinkage = 1 - s.exposure / (s.exposure + beta)

        # Excess load: events above what this surface's exposure alone predicts,
        # computed from the shrunk rate so thin surfaces cannot fake a spike.
        excess_events = (shrunk_rate / PER_1K) * s.exposure - expected
        excess_hours = excess_events * s.cost_per_event

        # Annualized hours recoverable if a fix lands and holds.
        value = excess_hours * s.fix_effectiveness * (365 / 90)

        rows.append(
            {
                "surface": s,
                "expected": expected,
                "raw_rate": raw_rate,
                "z_poisson": z_poisson,
                "z_nb": z_nb,
                "shrunk_rate": shrunk_rate,
                "shrinkage": shrinkage,
                "excess_events": excess_events,
                "excess_hours": excess_hours,
                "value": value,
                "roi": value / s.effort,
            }
        )
    return rows, (m, v, alpha, beta)


def rank_of(rows, key, name):
    order = sorted(rows, key=lambda r: r[key], reverse=True)
    return next(i + 1 for i, r in enumerate(order) if r["surface"].name == name)


def table(headers, body):
    widths = [max(len(str(h)), *(len(str(r[i])) for r in body)) for i, h in enumerate(headers)]
    line = "| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    out = [line, rule]
    for r in body:
        out.append("| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)) + " |")
    return "\n".join(out)


def main():
    rows, (m, v, alpha, beta) = analyze(SURFACES)

    print(f"Population rate m      : {m * PER_1K:.3f} events per 1,000 workspace-months")
    print(f"Between-surface var v  : {v:.3e}")
    print(f"Gamma prior            : alpha={alpha:.3f}, beta={beta:.1f} workspace-months")
    print(f"Dispersion check       : var/mean at median exposure = "
          f"{1 + 44_000 * v / m:.1f}x Poisson\n")

    print("Step 1-3: counts, rates, and the two z-scores\n")
    print(
        table(
            ["Surface", "Events", "Exposure", "Rate/1k", "Expected", "z (Poisson)", "z (NB)"],
            [
                [
                    r["surface"].name,
                    r["surface"].tickets,
                    f"{r['surface'].exposure:,.0f}",
                    f"{r['raw_rate']:.2f}",
                    f"{r['expected']:.1f}",
                    f"{r['z_poisson']:+.1f}",
                    f"{r['z_nb']:+.2f}",
                ]
                for r in rows
            ],
        )
    )

    print("\nStep 4-6: shrinkage, excess load, and value\n")
    print(
        table(
            ["Surface", "Rate/1k", "Shrunk/1k", "Pull", "Excess ev.", "Excess hrs", "Ann. hrs", "Effort", "Hrs/effort"],
            [
                [
                    r["surface"].name,
                    f"{r['raw_rate']:.2f}",
                    f"{r['shrunk_rate']:.2f}",
                    f"{r['shrinkage'] * 100:.0f}%",
                    f"{r['excess_events']:+.0f}",
                    f"{r['excess_hours']:+.0f}",
                    f"{r['value']:+.0f}",
                    f"{r['surface'].effort:.0f}",
                    f"{r['roi']:+.0f}",
                ]
                for r in rows
            ],
        )
    )

    print("\nHow the ranking moves as each correction is applied\n")
    keys = [
        ("raw count", lambda r: r["surface"].tickets),
        ("raw rate", lambda r: r["raw_rate"]),
        ("z (Poisson)", lambda r: r["z_poisson"]),
        ("z (NB)", lambda r: r["z_nb"]),
        ("annualized hours", lambda r: r["value"]),
        ("hours per effort", lambda r: r["roi"]),
    ]
    body = []
    for label, fn in keys:
        order = sorted(rows, key=fn, reverse=True)
        body.append([label] + [order[i]["surface"].name for i in range(3)])
    print(table(["Ranked by", "1st", "2nd", "3rd"], body))

    print("\nConcentration of recoverable load\n")
    values = sorted((max(r["value"], 0.0) for r in rows), reverse=True)
    total = sum(values)
    for k in (1, 2, 3, 5):
        print(f"  top {k}: {sum(values[:k]) / total * 100:5.1f}% of recoverable hours")
    print(f"  Gini : {gini([max(r['value'], 0.0) for r in rows]):.2f}")


if __name__ == "__main__":
    main()
