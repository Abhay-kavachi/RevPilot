# Temporal Deferral / Organic Recovery

**File:** `docs/TEMPORAL_DEFERRAL.md`  
**Status:** PARTIALLY IMPLEMENTED — Research/Demo Simulation  
**Priority:** SMALL EXTENSION / FUTURE RESEARCH  
**Scope:** Introduces time as an explicit recovery decision variable

## Implementation Status

### IMPLEMENTED (Research/Demo Simulation)
- Deterministic temporal decision simulator (`app/economics/temporal.py`)
- Synthetic organic recovery curve with piecewise-linear interpolation
- Three-outcome decision logic: ACT_NOW / DEFER / STOP
- Timeline simulation across multiple time steps
- Demo script with 3 cases (`scripts/run_temporal.py`)
- 12 focused unit tests (`test_temporal.py`)
- All organic recovery probabilities explicitly labeled as SYNTHETIC

### NOT IMPLEMENTED (Production Features)
- Production `DEFERRED` state in the case state machine
- Production scheduler or cron for re-evaluation
- Real asynchronous re-evaluation via the worker
- Database schema changes (no `next_evaluation_at`, no `deferral_count` columns)
- Integration with the real executor pipeline

### FUTURE RESEARCH
- Production temporal state machine with safe state transitions
- Calibrated time-to-payment / survival model from real merchant data
- Kaplan-Meier survival curves for organic recovery estimation
- Customer-specific hazard models
- Merchant-specific temporal recovery estimates
- Integration with portfolio optimizer (DEFER as zero-cost alternative)

## 1. Purpose

Extend RevPilot so it can distinguish between:

- **STOP:** pursuing recovery is not economically justified within the allowed horizon; and
- **DEFER:** acting now is inferior to waiting and re-evaluating later.

The conceptual question becomes:

> **"Is this a bad recovery case, or is this simply the wrong time to intervene?"**

## 2. Problem Statement

The current `NO_ACTION` outcome may collapse two distinct economic situations:

1. There is no worthwhile intervention and no meaningful reason to wait.
2. Intervening now is inferior to waiting because the expected value of future/organic recovery may be higher.

A temporal decision layer would make that distinction explicit.

## 3. Conceptual Model

### STOP

The system should terminate the recovery path when:

- current candidate actions are not economically worthwhile; and
- the expected value of waiting within the permitted horizon does not justify another evaluation.

### DEFER

The system should defer when:

- intervention today is inferior to waiting; and
- waiting has positive expected economic value; and
- policy permits another evaluation within the maximum deferral horizon.

`DEFER` is therefore a **time-aware economic decision**, not simply a synonym for `NO_ACTION`.

## 4. Decision Semantics

Proposed outcomes:

- `ACTION` — intervene now.
- `DEFER` — take no intervention now; schedule re-evaluation.
- `STOP` — terminate recovery evaluation for this invoice.

Do not silently reinterpret existing `NO_ACTION` semantics without auditing every consumer.

If backwards compatibility is important, `NO_ACTION` may remain the external legacy label while mapping internally to `STOP`.

## 5. Organic Recovery Model — SYNTHETIC

RevPilot currently relies on a synthetic causal world model for ML evaluation.

Any organic-recovery probability introduced here is therefore **synthetic/demo behavior unless the repository contains real evidence**.

Illustrative synthetic structure:

\[
P_{organic}(t)
\]

where probability changes as time since failure changes.

Example only:

- Day 1: 15%
- Day 2: 5%
- Day 3: 1%
- Day 7: 0.1%

These values must be treated as configurable synthetic assumptions, not factual claims about customer behavior.

## 6. Time / Horizon Representation

Required concepts:

- `time_since_failure`
- `next_evaluation_at`
- `max_deferral_horizon`
- `deferral_count`

Waiting has:

- direct execution cost = ₹0
- direct friction = ₹0
- delay risk = a modeled penalty, where supported

The minimum implementation should not pretend to have perfect customer-survival knowledge.

## 7. Mathematical Formulation

For an active intervention `a`:

\[
ENR(a) = P(R \mid C,a)\times V - C_a - F_a - R_a
\]

For deferral:

\[
ENR(DEFER) = P(Organic\mid t_{next})\times V - Risk_{delay}
\]

The policy layer may select `DEFER` when:

\[
ENR(DEFER) > \max_a ENR(a)
\]

and:

\[
t_{elapsed} < Horizon_{max}
\]

and policy permits waiting.

This is the minimum conceptual model, not a claim of full survival-analysis fidelity.

## 8. Risk of Waiting

The most difficult modeling component is `Risk_delay`.

Potential contributors include:

- time value of money;
- increased probability of eventual failure;
- customer/churn risk;
- expiration of downstream payment opportunities.

For the minimum viable implementation, use only a clearly documented simple penalty consistent with the synthetic world.

Do not introduce a sophisticated survival model solely to make the concept look advanced.

## 9. Interaction with Existing Action-Conditioned ML

Two implementation strategies are possible.

### Preferred minimal path

Keep the existing action-conditioned predictor focused on real intervention actions and calculate the synthetic organic baseline in the economics layer.

### Optional unified model path

Allow the predictor to represent `DEFER`/`WAIT` as a decision state, but only if doing so fits the repository's current feature schema and evaluation framework without creating leakage or training-serving inconsistency.

The first strategy is safer for the current architecture.

## 10. Interaction with ENR

Waiting is evaluated as an economic alternative.

It should win only when:

- intervention options have lower ENR; and
- future/organic recovery value remains sufficiently positive; and
- policy allows waiting.

A negative active-action score alone is NOT enough to justify `DEFER`.

The system must compare `DEFER` with the available alternatives.

## 11. Interaction with Portfolio Optimization

`DEFER` can conceptually be treated as a zero-budget alternative, but care is required:

- it should not be allowed to crowd out a profitable action merely because its direct cost is zero;
- its ENR must reflect the expected value of waiting and any delay risk;
- portfolio optimization should continue to maximize total ENR under merchant budget constraints.

A useful interpretation is:

> The optimizer can conserve scarce recovery capital by deferring cases where waiting has higher expected economic value.

## 12. Inputs

Minimum:

- `invoice_id`
- `time_since_failure`
- `current_timestamp`
- `max_deferral_horizon`
- current candidate-action ENRs
- synthetic/configured organic recovery function
- delay-risk parameters

## 13. Outputs

Example:

```json
{
  "decision": "DEFER",
  "reason": "Expected value of waiting exceeds intervention value.",
  "enr_defer": 40.0,
  "best_action_enr": 35.0,
  "next_evaluation_at": "2026-09-05T09:00:00Z",
  "deferral_count": 1
}
```

Field names should match repository conventions.

## 14. State-Machine Changes

Conceptual flow:

```text
FAILED
  |
  v
EVALUATING
  |
  +---- ACTION_QUEUED
  |
  +---- DEFERRED
  |       |
  |       v
  |   RE-EVALUATING
  |       |
  |       +---- ACTION_QUEUED
  |       |
  |       +---- DEFERRED
  |       |
  |       +---- STOPPED
  |
  +---- STOPPED
```

Do not add a state transition until all existing state consumers have been audited.

## 15. Database / Schema Implications

Only if the existing schema is suitable:

`PaymentRecovery` or equivalent may gain:

- `status = DEFERRED`
- `next_evaluation_at`
- `deferral_count`

Do not create a new table solely for deferral.

## 16. Re-evaluation Mechanism

A deferred item must be returned to evaluation at or after `next_evaluation_at`.

Implementation choices should reuse existing infrastructure where possible:

- scheduler
- queue
- cron
- worker
- periodic job

Avoid introducing a new task framework.

If the repository has no reliable asynchronous mechanism, treat this feature as future research rather than forcing a fragile worker into the system.

## 17. UI / UX

Add a lightweight deferred state in the recovery queue.

Example:

> **Deferred**  
> Invoice #102  
> Reason: waiting currently has higher expected net value than intervention  
> Next evaluation: 12 hours

The UI should expose the economic reason, not merely a technical status.

A simulation/debug control such as:

`Simulate +24h`

is acceptable for a deterministic demo harness, but MUST remain clearly identified as a demo/test control.

## 18. Deterministic Synthetic Example

Example:

- Invoice value = ₹1,000
- Current time = 2 hours after failure
- Synthetic expected organic recovery in next 24h = 20%
- `ENR(DEFER)` = ₹200 minus documented delay risk
- Payment Link:
  - predicted success = 22%
  - cost = ₹50
  - `ENR` = ₹170

Decision:

`DEFER`

because waiting has higher expected economic value under the synthetic assumptions.

The final implementation must calculate numbers from actual configured rules rather than hardcoding the displayed result.

## 19. Example: Timing Matters

Illustrative synthetic case:

A payment fails at 11:00 PM because of `INSUFFICIENT_FUNDS`.

The synthetic world model assigns:

- very low immediate SMS conversion;
- materially higher organic recovery probability the following morning.

RevPilot may therefore defer rather than interrupt the customer immediately.

This is a demonstration of temporal decisioning, not a claim about real-world salary cycles or customer behavior.

## 20. Maximum Deferral Horizon

Policy must bound waiting.

Example:

`MAX_DEFERRAL_DAYS = 3`

After the horizon is reached, the system must re-evaluate and select:

- an economically worthwhile action; or
- `STOP`.

Never allow indefinite deferral loops.

## 21. Re-evaluation Rules

On every re-evaluation:

1. Refresh time-dependent inputs.
2. Recompute the organic/waiting value.
3. Recompute active candidate-action ENRs.
4. Compare them.
5. Check policy/horizon limits.
6. Select `ACTION`, `DEFER`, or `STOP`.

The decision must therefore remain dynamic rather than being locked when the original failure occurs.

## 22. Edge Cases

- `max_deferral_horizon = 0`
- no organic recovery probability
- waiting has negative ENR
- active action has positive ENR
- repeated deferral
- horizon reached
- missing `next_evaluation_at`
- scheduler outage
- duplicate re-evaluation
- concurrent evaluation
- invoice paid while deferred
- invoice state changed by webhook while deferred

The existing concurrency/idempotency rules must continue to apply.

## 23. Security / Abuse Considerations

Deferral must not become a mechanism for silently avoiding collection or manipulating financial state.

Every deferral decision should be:

- policy-bounded;
- auditable;
- idempotent;
- safe under concurrent events.

A paid invoice must never be re-queued for recovery merely because it was previously deferred.

## 24. Audit Trail

Log the counterfactuals that justify the decision.

Example:

> Deferred at T+2h because `ENR(DEFER)=₹40` exceeded `ENR(SMS)=₹35`; next evaluation at T+24h.

At re-evaluation, retain the new comparison.

This is especially important because deferral is intentionally choosing not to execute now.

## 25. Failure Modes

### Scheduler failure

Deferred records may become overdue.

Required behavior:

- detect overdue deferred records;
- surface an operational alert;
- safely re-evaluate when the worker recovers.

### Concurrency

A deferred record may be paid before the scheduler re-queues it.

The re-evaluation must verify current state before action.

### Model/configuration failure

If the waiting-value calculation is unavailable, fail closed to the repository's safe policy rather than inventing an ENR.

## 26. Test Plan

### State tests
- Deferred items are not executed immediately.
- Paid deferred items cannot be executed.
- Deferral transitions preserve valid state-machine invariants.

### Time/decay tests
- Advancing simulated time changes waiting value.
- Once the horizon is exceeded, indefinite deferral is impossible.

### Decision tests
- `DEFER` wins only when its computed ENR exceeds alternatives.
- A positive-ENR active action beats a lower-value deferral.
- No organic recovery value leads to `STOP` or an active action depending on policy.

### Reliability
- duplicate scheduler ticks are idempotent;
- concurrent state changes are safe;
- existing full test suite remains passing.

## 27. Mathematical Limitations

The largest uncertainty is `Risk_delay`.

Without rich historical data, the project should not claim to know the true long-term effect of waiting.

Minimum implementation should therefore:

- label synthetic assumptions;
- keep the delay-risk function explicit;
- avoid overconfident real-world claims.

Future research could use survival analysis or calibrated merchant-specific time-to-payment models.

## 28. Acceptance Criteria

The feature is complete only when:

1. A valid `DEFER` decision can be produced from explicit economics.
2. Deferral schedules a deterministic re-evaluation.
3. Re-evaluation refreshes time-dependent inputs.
4. Deferral cannot continue beyond policy limits.
5. State/concurrency/idempotency rules remain intact.
6. The audit trail records the economic reason.
7. Synthetic/demo assumptions are explicitly labeled.
8. Existing execution security remains unchanged.

## 29. What Should Remain Future Research

Do not block the MVP on:

- Kaplan-Meier survival curves;
- customer-specific hazard models;
- sophisticated real-time hazard estimation;
- long-term LTV/churn modeling;
- reinforcement learning;
- LLM-based timing decisions.

These can remain research directions.

## 30. Why This Matters to RevPilot

Current RevPilot asks:

> **"Should I act?"**

Temporal Deferral introduces:

> **"Should I act now?"**

That difference turns time into an explicit economic variable.

It also makes the distinction between two forms of inaction precise:

- **STOP:** do not spend recovery resources.
- **DEFER:** preserve the option to recover later because waiting currently has higher expected economic value.

This is the intended conceptual extension.

# Strategic Positioning

Deferral is conceptually powerful but operationally larger than Shadow Price because it touches state, scheduling, re-evaluation, and synthetic temporal assumptions.

Therefore:

**Recommended priority:**

1. Shadow Price — BUILD NOW
2. Temporal Deferral — SMALL EXTENSION if the current infrastructure supports it safely
3. Otherwise keep Temporal Deferral as future research / architecture direction
