#!/usr/bin/env python3
"""Reproduces the closed-loop validation example in signal-to-cause-whitepaper.md.

Answers the question "did the fix actually work, or did the number just move?"
using a difference-in-differences estimate on a staged rollout, which is the
natural experiment we already generate every time we ship to some customers
before others.

Pure standard library. Usage:
    python3 validation_example.py
"""

import math

# 12 weeks before and 12 weeks after the fix shipped to the treated cohort.
# Exposure is workspace-weeks, so the cohorts do not have to be the same size.
TREATED_PRE = {"events": 318, "exposure": 9_600}
TREATED_POST = {"events": 121, "exposure": 9_900}
CONTROL_PRE = {"events": 274, "exposure": 11_200}
CONTROL_POST = {"events": 205, "exposure": 11_400}

# Over-dispersion factor, estimated from the residual deviance of the weekly
# counts. 1.0 would mean pure Poisson; support data is never pure Poisson.
DISPERSION = 3.4

# What the prioritization model claimed before the work started. Recording this
# up front is what makes the comparison a test rather than a story.
PREDICTED_REDUCTION = 0.55


def rate(cell):
    return cell["events"] / cell["exposure"]


def main():
    r_tp, r_tr = rate(TREATED_PRE), rate(TREATED_POST)
    r_cp, r_cr = rate(CONTROL_PRE), rate(CONTROL_POST)

    print("Event rates per 1,000 workspace-weeks\n")
    print(f"  treated  before {r_tp * 1000:6.2f}   after {r_tr * 1000:6.2f}   "
          f"raw change {(r_tr / r_tp - 1) * 100:+.0f}%")
    print(f"  control  before {r_cp * 1000:6.2f}   after {r_cr * 1000:6.2f}   "
          f"raw change {(r_cr / r_cp - 1) * 100:+.0f}%")

    # The treated group's raw change is contaminated by whatever moved the
    # control group too (seasonality, install-base growth, a support process
    # change). Subtracting the control trend in log space removes it.
    log_rr = (math.log(r_tr) - math.log(r_tp)) - (math.log(r_cr) - math.log(r_cp))
    se = math.sqrt(
        DISPERSION
        * (
            1 / TREATED_POST["events"]
            + 1 / TREATED_PRE["events"]
            + 1 / CONTROL_POST["events"]
            + 1 / CONTROL_PRE["events"]
        )
    )
    rr = math.exp(log_rr)
    lo, hi = math.exp(log_rr - 1.96 * se), math.exp(log_rr + 1.96 * se)

    print("\nDifference-in-differences\n")
    print(f"  rate ratio          {rr:.3f}   (95% CI {lo:.3f} to {hi:.3f})")
    print(f"  reduction           {(1 - rr) * 100:.0f}%   "
          f"(95% CI {(1 - hi) * 100:.0f}% to {(1 - lo) * 100:.0f}%)")
    print(f"  naive before/after  {(1 - r_tr / r_tp) * 100:.0f}%   "
          f"<- overstates by {((1 - r_tr / r_tp) - (1 - rr)) * 100:.0f} points")

    # Events avoided in the post window, on the treated cohort only.
    counterfactual = r_tp * (r_cr / r_cp) * TREATED_POST["exposure"]
    avoided = counterfactual - TREATED_POST["events"]
    print(f"\n  counterfactual events without the fix  {counterfactual:.0f}")
    print(f"  observed events                        {TREATED_POST['events']}")
    print(f"  events avoided                         {avoided:.0f}")

    print("\nPrediction scorecard\n")
    print(f"  predicted reduction {PREDICTED_REDUCTION * 100:.0f}%")
    print(f"  realized reduction  {(1 - rr) * 100:.0f}%")
    inside = lo <= 1 - PREDICTED_REDUCTION <= hi
    print(f"  prediction inside the confidence interval: {'yes' if inside else 'no'}")
    print("\n  A miss is not a failure of the program. It is a calibration signal:")
    print("  feed the ratio of realized to predicted back into the effectiveness")
    print("  term of the next ranking so the model learns how optimistic it is.")


if __name__ == "__main__":
    main()
