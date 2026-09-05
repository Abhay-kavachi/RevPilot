"""
Temporal Deferral Simulator — RESEARCH / DEMO SCRIPT

Demonstrates RevPilot's temporal economic reasoning:
"Should I act now, or is waiting economically better?"

ALL organic-recovery probabilities are SYNTHETIC demo assumptions.
They do NOT represent real-world customer payment behavior.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.economics.engine import EconomicEngine
from app.economics.temporal import TemporalDeferralSimulator

SEPARATOR = "=" * 89
THIN_SEP = "-" * 89


def print_temporal_result(result, step_label=""):
    label = f" [{step_label}]" if step_label else ""
    print(SEPARATOR)
    print(f"TEMPORAL DECISION SIMULATOR{label}  [RESEARCH / SIMULATION]")
    print(SEPARATOR)
    print(f"Payment Value         : {result.amount_at_risk_paise / 100:,.2f} INR")
    print(f"Time Since Failure    : {result.hours_since_failure:.0f}h")
    print(f"Max Deferral Horizon  : {result.max_horizon_hours}h")
    print()

    # Best active intervention
    print("  ACT NOW")
    if result.best_action:
        a = result.best_action
        print(f"    Action              : {a.action_type}")
        print(f"    Success Probability : {a.success_probability:.4f}")
        print(f"    Cost                : {a.cost / 100:.2f} INR")
        print(f"    Expected Net Rec.   : {a.final_enr / 100:.2f} INR")
    else:
        print("    No economically viable intervention.")
    print()

    # Deferral alternative
    print("  WAIT (Synthetic Organic Recovery Assumption)")
    if result.deferral:
        d = result.deferral
        print(f"    Wait Period         : +{d.wait_hours}h")
        print(f"    Organic Probability : {d.organic_probability:.4f}  [SYNTHETIC]")
        print(f"    Delay Risk          : {d.delay_risk_paise / 100:.2f} INR")
        print(f"    Expected Net Rec.   : {d.enr_defer_paise / 100:.2f} INR")
    else:
        print("    Beyond maximum deferral horizon.")
    print()

    # Decision
    decision_icon = {"ACT_NOW": ">>", "DEFER": "||", "STOP": "XX"}.get(result.decision, "??")
    print(f"  RECOMMENDATION: [{decision_icon}] {result.decision}")
    print(f"  Reason: {result.reason}")
    print(SEPARATOR)
    print()


def main():
    engine = EconomicEngine()
    simulator = TemporalDeferralSimulator(
        max_horizon_hours=72,
        deferral_step_hours=24,
        delay_risk_paise=0,
    )

    # ──────────────────────────────────────────────────────────────────────
    # CASE 1: DEFER wins — organic recovery beats marginal intervention
    # ──────────────────────────────────────────────────────────────────────
    print("\n" + SEPARATOR)
    print("CASE 1: TEMPORAL DEFERRAL - Waiting beats intervention")
    print(SEPARATOR + "\n")

    # A very small invoice (INR 10) evaluated 0h post-failure.
    # We use a 6h deferral step so organic probability is still ~18%.
    # With high-risk context (3 recent failures), ML probabilities drop,
    # making action costs eat most of the expected value.
    sim_defer = TemporalDeferralSimulator(
        max_horizon_hours=72,
        deferral_step_hours=4,
        delay_risk_paise=0,
    )

    evals_1 = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=1000,   # 1000 paise = INR 10
        attempt_count=2,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=0.3,
        recent_30d_failures=3,
    )

    result_1 = sim_defer.evaluate(
        amount_at_risk_paise=1000,
        hours_since_failure=0.0,
        action_evaluations=evals_1,
    )
    print_temporal_result(result_1, "T+0h")

    # ──────────────────────────────────────────────────────────────────────
    # CASE 2: ACT NOW wins — high-value payment, action ENR dominates
    # ──────────────────────────────────────────────────────────────────────
    print(SEPARATOR)
    print("CASE 2: ACT NOW - Intervention clearly better than waiting")
    print(SEPARATOR + "\n")

    evals_2 = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=5000000,  # ₹50,000
        attempt_count=0,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=1.0,
        recent_30d_failures=0,
    )

    result_2 = simulator.evaluate(
        amount_at_risk_paise=5000000,
        hours_since_failure=2.0,
        action_evaluations=evals_2,
    )
    print_temporal_result(result_2, "T+2h")

    # ──────────────────────────────────────────────────────────────────────
    # CASE 3: TIME SIMULATION — Watch the decision change over 4 steps
    # ──────────────────────────────────────────────────────────────────────
    print(SEPARATOR)
    print("CASE 3: TIME SIMULATION - Decision evolution over 72h")
    print("        (INR 10 payment, simulating +24h steps)")
    print(SEPARATOR + "\n")

    timeline = simulator.simulate_timeline(
        amount_at_risk_paise=1000,
        action_evaluations=evals_1,
        start_hours=0.0,
        steps=4,
    )

    for i, step_result in enumerate(timeline):
        print_temporal_result(step_result, f"Step {i + 1}")


if __name__ == "__main__":
    main()
