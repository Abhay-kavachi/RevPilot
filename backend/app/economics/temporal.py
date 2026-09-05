"""
Temporal Deferral Simulator — RESEARCH / DEMO ONLY

Provides a deterministic simulation of temporal economic reasoning:
"Should I act now, or is waiting economically better?"

This module is architecturally isolated from the production execution path.
It does NOT:
- queue real Razorpay actions
- modify payment recovery state
- invoke the executor
- alter webhook logic
- bypass policy or RBAC

All organic-recovery probabilities are SYNTHETIC research/demo assumptions,
not trained from real merchant behavior.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from app.economics.engine import ActionEvaluation


# ─── Synthetic Organic Recovery Model ────────────────────────────────────────
# These are SYNTHETIC demo assumptions. They do NOT represent real-world
# customer payment behavior or Razorpay merchant data.

SYNTHETIC_ORGANIC_RECOVERY_CURVE = {
    # hours_since_failure -> synthetic organic recovery probability
    0: 0.25,
    2: 0.22,
    6: 0.18,
    12: 0.15,
    24: 0.10,
    48: 0.05,
    72: 0.02,
    96: 0.005,
}

DEFAULT_MAX_DEFERRAL_HORIZON_HOURS = 72
DEFAULT_DEFERRAL_STEP_HOURS = 24


def _interpolate_organic_probability(hours_since_failure: float) -> float:
    """
    Piecewise-linear interpolation over the synthetic organic recovery curve.
    Returns 0.0 beyond the last defined point.
    """
    breakpoints = sorted(SYNTHETIC_ORGANIC_RECOVERY_CURVE.keys())
    if hours_since_failure <= breakpoints[0]:
        return SYNTHETIC_ORGANIC_RECOVERY_CURVE[breakpoints[0]]
    if hours_since_failure >= breakpoints[-1]:
        return SYNTHETIC_ORGANIC_RECOVERY_CURVE[breakpoints[-1]]

    for i in range(len(breakpoints) - 1):
        t0, t1 = breakpoints[i], breakpoints[i + 1]
        if t0 <= hours_since_failure <= t1:
            p0 = SYNTHETIC_ORGANIC_RECOVERY_CURVE[t0]
            p1 = SYNTHETIC_ORGANIC_RECOVERY_CURVE[t1]
            frac = (hours_since_failure - t0) / (t1 - t0)
            return p0 + frac * (p1 - p0)

    return 0.0


# ─── Result Types ────────────────────────────────────────────────────────────

@dataclass
class DeferralEvaluation:
    """Economic evaluation of the DEFER alternative at a specific future time."""
    wait_hours: int
    future_hours_since_failure: float
    organic_probability: float
    expected_value_paise: int
    delay_risk_paise: int
    enr_defer_paise: int


@dataclass
class TemporalDecisionResult:
    """Complete temporal decision output."""
    decision: str  # "ACT_NOW", "DEFER", or "STOP"
    reason: str

    # Case context
    amount_at_risk_paise: int
    hours_since_failure: float

    # Best active intervention
    best_action: Optional[ActionEvaluation]
    best_action_enr_paise: int

    # Deferral evaluation (None if STOP or ACT_NOW without viable deferral)
    deferral: Optional[DeferralEvaluation]

    # Simulation metadata
    max_horizon_hours: int
    is_synthetic: bool = True


# ─── Temporal Decision Simulator ─────────────────────────────────────────────

class TemporalDeferralSimulator:
    """
    Deterministic research/demo simulator for temporal economic reasoning.

    Compares:
      ENR(ACT_NOW) = best candidate action ENR
      ENR(DEFER)   = P(organic | future_time) * V - delay_risk

    Chooses DEFER only when ENR(DEFER) > ENR(ACT_NOW) > 0
    and the maximum deferral horizon has not been exceeded.

    IMPORTANT: All organic recovery probabilities are synthetic.
    This simulator never invokes the real executor.
    """

    def __init__(
        self,
        max_horizon_hours: int = DEFAULT_MAX_DEFERRAL_HORIZON_HOURS,
        deferral_step_hours: int = DEFAULT_DEFERRAL_STEP_HOURS,
        delay_risk_paise: int = 0,
    ):
        self.max_horizon_hours = max_horizon_hours
        self.deferral_step_hours = deferral_step_hours
        self.delay_risk_paise = delay_risk_paise

    def evaluate(
        self,
        amount_at_risk_paise: int,
        hours_since_failure: float,
        action_evaluations: List[ActionEvaluation],
    ) -> TemporalDecisionResult:
        """
        Evaluate whether to ACT_NOW, DEFER, or STOP.

        Args:
            amount_at_risk_paise: Invoice value in paise.
            hours_since_failure: Current elapsed hours since payment failure.
            action_evaluations: Pre-computed action evaluations from EconomicEngine.

        Returns:
            TemporalDecisionResult with the decision and full economic trace.
        """
        # Find best active intervention
        positive_actions = [a for a in action_evaluations if a.final_enr > 0]
        
        if positive_actions:
            best_action = max(positive_actions, key=lambda a: a.final_enr)
            best_action_enr = best_action.final_enr
        else:
            best_action = None
            best_action_enr = 0

        # Evaluate deferral alternative
        future_hours = hours_since_failure + self.deferral_step_hours
        within_horizon = future_hours <= self.max_horizon_hours

        deferral_eval = None
        if within_horizon:
            organic_prob = _interpolate_organic_probability(future_hours)
            ev_defer = int(amount_at_risk_paise * organic_prob)
            enr_defer = ev_defer - self.delay_risk_paise
            
            deferral_eval = DeferralEvaluation(
                wait_hours=self.deferral_step_hours,
                future_hours_since_failure=future_hours,
                organic_probability=organic_prob,
                expected_value_paise=ev_defer,
                delay_risk_paise=self.delay_risk_paise,
                enr_defer_paise=enr_defer,
            )

        # Decision logic
        if best_action_enr <= 0 and (deferral_eval is None or deferral_eval.enr_defer_paise <= 0):
            # Neither acting nor waiting has positive expected value
            return TemporalDecisionResult(
                decision="STOP",
                reason="No economically worthwhile recovery path remains within the allowed horizon.",
                amount_at_risk_paise=amount_at_risk_paise,
                hours_since_failure=hours_since_failure,
                best_action=best_action,
                best_action_enr_paise=best_action_enr,
                deferral=deferral_eval,
                max_horizon_hours=self.max_horizon_hours,
            )

        if deferral_eval is not None and deferral_eval.enr_defer_paise > best_action_enr:
            return TemporalDecisionResult(
                decision="DEFER",
                reason=(
                    f"Expected value of waiting {self.deferral_step_hours}h "
                    f"({deferral_eval.enr_defer_paise / 100:.2f} INR) exceeds "
                    f"best intervention ({best_action_enr / 100:.2f} INR). "
                    f"Synthetic organic recovery assumption."
                ),
                amount_at_risk_paise=amount_at_risk_paise,
                hours_since_failure=hours_since_failure,
                best_action=best_action,
                best_action_enr_paise=best_action_enr,
                deferral=deferral_eval,
                max_horizon_hours=self.max_horizon_hours,
            )

        return TemporalDecisionResult(
            decision="ACT_NOW",
            reason=(
                f"Best intervention ENR ({best_action_enr / 100:.2f} INR) "
                f"exceeds or equals deferral value. Act immediately."
            ),
            amount_at_risk_paise=amount_at_risk_paise,
            hours_since_failure=hours_since_failure,
            best_action=best_action,
            best_action_enr_paise=best_action_enr,
            deferral=deferral_eval,
            max_horizon_hours=self.max_horizon_hours,
        )

    def simulate_timeline(
        self,
        amount_at_risk_paise: int,
        action_evaluations: List[ActionEvaluation],
        start_hours: float = 0.0,
        steps: int = 4,
    ) -> List[TemporalDecisionResult]:
        """
        Simulate decisions across multiple time steps.
        Useful for demonstrating how the temporal decision changes over time.

        Returns a list of TemporalDecisionResult, one per time step.
        """
        results = []
        current_hours = start_hours
        for _ in range(steps):
            result = self.evaluate(amount_at_risk_paise, current_hours, action_evaluations)
            results.append(result)
            current_hours += self.deferral_step_hours
        return results
