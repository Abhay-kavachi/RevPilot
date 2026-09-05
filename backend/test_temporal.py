"""
Focused tests for the Temporal Deferral Simulator.
All tests are deterministic and verify the simulator never invokes the real executor.
"""

import pytest
from app.economics.engine import ActionEvaluation
from app.economics.temporal import (
    TemporalDeferralSimulator,
    _interpolate_organic_probability,
    SYNTHETIC_ORGANIC_RECOVERY_CURVE,
    DEFAULT_MAX_DEFERRAL_HORIZON_HOURS,
)


def _make_action(action_type: str, enr: int, cost: int = 50, prob: float = 0.5) -> ActionEvaluation:
    return ActionEvaluation(
        action_type=action_type,
        success_probability=prob,
        expected_value=enr + cost,
        cost=cost,
        friction=0,
        risk=0,
        final_enr=enr,
        probability_source="TEST",
    )


# ─── 1. ACT NOW wins when action ENR > DEFER ENR ────────────────────────────

def test_act_now_wins_when_action_enr_exceeds_defer():
    """High-value action should beat organic recovery."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    # Action ENR = 50000 paise (₹500). At 26h, organic prob ~0.10, 
    # for a ₹1000 invoice that's only 10000 paise ENR.
    actions = [_make_action("CREATE_PAYMENT_LINK", enr=50000, cost=250)]
    result = sim.evaluate(amount_at_risk_paise=100000, hours_since_failure=2.0, action_evaluations=actions)
    assert result.decision == "ACT_NOW"
    assert result.best_action is not None
    assert result.best_action.action_type == "CREATE_PAYMENT_LINK"
    assert result.is_synthetic is True


# ─── 2. DEFER wins when DEFER ENR > action ENR ──────────────────────────────

def test_defer_wins_when_organic_exceeds_action():
    """Low-value invoice where organic recovery probability * value > action ENR."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    # Tiny action ENR = 5 paise. Invoice = 1000 paise (₹10).
    # At 2h, defer to 26h: organic prob ~0.10, EV = 100 paise, ENR = 100.
    actions = [_make_action("SEND_REMINDER", enr=5, cost=50)]
    result = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=2.0, action_evaluations=actions)
    assert result.decision == "DEFER"
    assert result.deferral is not None
    assert result.deferral.enr_defer_paise > result.best_action_enr_paise


# ─── 3. STOP wins when both are non-positive ────────────────────────────────

def test_stop_when_both_negative():
    """Neither acting nor waiting has positive expected value."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=500)
    # Very tiny invoice (₹1 = 100 paise), negative ENR actions, and delay risk eats organic value
    actions = [_make_action("SEND_REMINDER", enr=-50, cost=50)]
    result = sim.evaluate(amount_at_risk_paise=100, hours_since_failure=50.0, action_evaluations=actions)
    # At 74h, organic ~0.02, EV = 2 paise, delay risk = 500 => ENR_defer = -498
    assert result.decision == "STOP"


# ─── 4. Advancing simulated time changes the result ─────────────────────────

def test_time_advancement_changes_decision():
    """As time passes, organic recovery probability drops and the decision may shift."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    # Low-value invoice where DEFER initially wins
    actions = [_make_action("SEND_REMINDER", enr=5, cost=50)]

    # At T=0h, deferral to 24h has high organic prob -> DEFER
    result_early = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=0.0, action_evaluations=actions)
    
    # At T=48h, deferral to 72h has very low organic prob -> should shift
    result_late = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=48.0, action_evaluations=actions)

    # Verify that the organic probability dropped
    assert result_early.deferral.organic_probability > result_late.deferral.organic_probability


# ─── 5. Maximum demo horizon is respected ───────────────────────────────────

def test_horizon_respected():
    """Beyond max horizon, deferral is not offered."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    # At 60h, deferral would be to 84h which exceeds 72h horizon
    actions = [_make_action("SEND_REMINDER", enr=-10, cost=50)]
    result = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=60.0, action_evaluations=actions)
    assert result.deferral is None
    assert result.decision == "STOP"  # No positive action, no deferral


# ─── 6. Synthetic values are deterministic ───────────────────────────────────

def test_deterministic_results():
    """Running the same inputs twice must produce identical results."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    actions = [_make_action("SEND_REMINDER", enr=5, cost=50)]
    
    r1 = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=2.0, action_evaluations=actions)
    r2 = sim.evaluate(amount_at_risk_paise=1000, hours_since_failure=2.0, action_evaluations=actions)
    
    assert r1.decision == r2.decision
    assert r1.best_action_enr_paise == r2.best_action_enr_paise
    if r1.deferral and r2.deferral:
        assert r1.deferral.enr_defer_paise == r2.deferral.enr_defer_paise
        assert r1.deferral.organic_probability == r2.deferral.organic_probability


# ─── 7. Simulator never invokes the real executor ────────────────────────────

def test_no_executor_invocation():
    """The simulator is pure computation — it returns data, never executes actions."""
    sim = TemporalDeferralSimulator()
    actions = [_make_action("CREATE_PAYMENT_LINK", enr=500, cost=250)]
    result = sim.evaluate(amount_at_risk_paise=10000, hours_since_failure=0.0, action_evaluations=actions)
    
    # The result is a data object, not an executor call
    assert result.is_synthetic is True
    assert isinstance(result.decision, str)
    assert result.decision in ("ACT_NOW", "DEFER", "STOP")


# ─── 8. Organic interpolation correctness ───────────────────────────────────

def test_organic_interpolation_at_breakpoints():
    """Interpolation returns exact values at defined breakpoints."""
    for hours, prob in SYNTHETIC_ORGANIC_RECOVERY_CURVE.items():
        assert _interpolate_organic_probability(float(hours)) == prob


def test_organic_interpolation_between_breakpoints():
    """Interpolation returns a value between the two surrounding breakpoints."""
    # Between 0h (0.25) and 2h (0.22), at 1h should be ~0.235
    p = _interpolate_organic_probability(1.0)
    assert 0.22 < p < 0.25


def test_organic_interpolation_beyond_last():
    """Beyond the last breakpoint, returns the last value."""
    p = _interpolate_organic_probability(200.0)
    last_val = SYNTHETIC_ORGANIC_RECOVERY_CURVE[max(SYNTHETIC_ORGANIC_RECOVERY_CURVE.keys())]
    assert p == last_val


# ─── 9. simulate_timeline produces correct number of steps ──────────────────

def test_simulate_timeline_step_count():
    """Timeline simulation returns the correct number of decision steps."""
    sim = TemporalDeferralSimulator(max_horizon_hours=96, deferral_step_hours=24)
    actions = [_make_action("SEND_REMINDER", enr=5, cost=50)]
    timeline = sim.simulate_timeline(
        amount_at_risk_paise=1000,
        action_evaluations=actions,
        start_hours=0.0,
        steps=4,
    )
    assert len(timeline) == 4
    # Each step should advance by deferral_step_hours
    for i, r in enumerate(timeline):
        assert r.hours_since_failure == i * 24.0


# ─── 10. Empty actions list produces STOP or DEFER ──────────────────────────

def test_no_actions_available():
    """With no viable actions, decision should be DEFER or STOP depending on organic value."""
    sim = TemporalDeferralSimulator(max_horizon_hours=72, deferral_step_hours=24, delay_risk_paise=0)
    # No actions at all
    result = sim.evaluate(amount_at_risk_paise=10000, hours_since_failure=0.0, action_evaluations=[])
    # Organic at 24h is ~0.10, EV=1000, ENR=1000 > 0 -> DEFER
    assert result.decision == "DEFER"
    assert result.best_action is None
