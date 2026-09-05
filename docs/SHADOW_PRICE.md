# Shadow Price of Recovery Budget

**File:** `docs/SHADOW_PRICE.md`  
**Status:** Proposed integration spec  
**Priority:** BUILD NOW  
**Scope:** Small economic extension to the existing RevPilot portfolio optimizer

## 1. Purpose

Extend RevPilot so it can quantify the **marginal expected economic value of relaxing the merchant's recovery-budget constraint**.

The existing portfolio optimizer answers:

> "Given budget B, where should recovery capital be deployed?"

This extension adds:

> "What additional expected net recovery becomes available if the merchant increases budget from B to B + Δ?"

The feature should remain an explanatory/economic layer. It must not alter the critical financial execution path by itself.

## 2. Problem Statement

The Multiple-Choice Knapsack Problem (MCKP) optimizer maximizes Expected Net Return (ENR) subject to a fixed recovery budget `B`.

A constrained optimum can hide an economically valuable fact: profitable interventions may remain excluded solely because the budget constraint prevents them from fitting.

The current optimizer therefore tells the merchant **what to fund**, but not **what the constraint itself is costing**.

## 3. Why the Existing Portfolio Optimizer Is Insufficient

The portfolio optimizer produces a best feasible allocation under the current budget. It does not expose the marginal value of relaxing that constraint.

For a discrete portfolio, a merchant may be at a budget level where a small additional amount of capital unlocks a materially better feasible allocation.

That opportunity should be measurable rather than left implicit.

## 4. Conceptual Definition

The extension introduces a **Discrete Marginal Budget Value**.

Let:

- `Z(B)` = maximum total ENR achievable by the existing portfolio optimizer under budget `B`
- `Δ` = an explicitly defined budget increment
- `Z(B + Δ)` = maximum total ENR under the relaxed budget

Then:

$$MV_{\Delta} = \frac{Z(B+\Delta)-Z(B)}{\Delta}$$

Interpretation:

> expected additional net recovery unlocked per additional rupee of recovery budget for the selected increment.

## 5. Mathematical Honesty

In continuous optimization, a shadow price is associated with a dual variable/Lagrange multiplier.

RevPilot's portfolio optimization is discrete. Actions cannot generally be fractionally executed, so the objective is stepwise rather than differentiable everywhere.

Therefore the product MUST NOT casually claim that `MV_Δ` is the exact continuous Lagrange multiplier.

Preferred terminology:

- **Discrete Marginal Budget Value**
- **Marginal Budget Value**
- **Discrete Shadow Price** (only with explanatory qualification)

Avoid presenting it as a continuous derivative unless the implementation actually establishes that interpretation.

## 6. Relationship to Multiple-Choice Knapsack

The portfolio optimizer chooses one valid action/state per invoice while respecting total budget.

Because feasible allocations are discrete:

- relaxing the budget by a small amount may unlock nothing;
- relaxing it may unlock one action;
- or a larger increment may unlock a different combination whose total ENR is better than the obvious next rejected item.

Therefore the most defensible implementation uses the **actual optimizer objective delta**, not merely the highest `ΔENR / ΔCost` rejected item.

## 7. Calculation Strategy

### Preferred strategy: optimizer re-solve

1. Run the existing optimizer at budget `B`.
2. Record `Z(B)`.
3. Choose an explicit increment `Δ` according to a documented policy/configuration.
4. Run the same optimizer at budget `B + Δ`.
5. Record `Z(B + Δ)`.
6. Compute `MV_Δ = (Z(B+Δ)-Z(B))/Δ`.
7. Identify the budget extension and incremental portfolio value responsible for the change.
8. Return a structured economic explanation without changing the base allocation.

### Optional secondary insight

The implementation may also identify the **minimum budget unlock** that first changes the optimal portfolio, provided that this can be computed efficiently and deterministically.

Do not use a greedy rejected-item ratio as the authoritative shadow-price calculation unless repository-level analysis proves that it is equivalent for the specific optimizer.

## 8. Inputs

Required:

- `portfolio_items`
- `current_budget`

Recommended configuration:

- `shadow_price_delta` (budget increment, in paise internally)
- optional maximum calculation latency

All money should follow the repository's established monetary representation.

## 9. Outputs

Proposed result shape:

```json
{
  "shadow_price_metrics": {
    "current_budget": 50.0,
    "relaxed_budget": 60.0,
    "marginal_budget_value": 4.5,
    "incremental_expected_net_recovery": 45.0,
    "budget_unlock": 10.0,
    "portfolio_changed": true,
    "interpretation": "An additional ₹10 budget unlocks approximately ₹45 of expected net recovery."
  }
}
```

Field names may be adapted to the existing repository conventions.

The canonical concept is:

`incremental_expected_net_recovery / budget_increment`

## 10. Data Model / Persistence

Prefer **not** to add persistent schema fields unless the repository already persists optimization-run summaries.

If optimization runs are already logged, optional fields include:

- `marginal_budget_value_ratio`
- `incremental_expected_net_recovery`
- `required_budget_unlock`

Do not introduce a new database table only for this feature.

## 11. Backend Integration

Add the smallest possible method at the existing economics/portfolio boundary, for example:

```python
calculate_marginal_budget_value(...)
```

Requirements:

- reuse the existing optimizer;
- preserve deterministic behavior;
- fail independently from the base optimizer where practical;
- never execute payment actions;
- never bypass policy.

The feature should run after the base portfolio calculation and remain informational.

## 12. API Integration

Extend the existing optimization summary/result endpoint rather than creating a parallel API unless the repository structure makes that inappropriate.

Example:

```json
{
  "shadow_price_metrics": {
    "marginal_value_per_inr": 4.5,
    "budget_increment": 10.0,
    "incremental_expected_net_recovery": 45.0
  }
}
```

If calculation is unavailable because of timeout or configuration, return a safe `null`/unavailable representation rather than failing the primary portfolio result.

## 13. UI / UX

The UI should make the economic insight obvious without turning it into a marketing feature.

Suggested component:

> **Recovery Budget:** ₹50.00  
> **Expected Net Recovery:** ₹145.20  
> **Marginal Budget Value:** ₹4.50 per ₹1  
> **Additional Budget Opportunity:** ≈ ₹45.00 expected net recovery  
> **Budget Unlock:** ₹10.00

Preferred action label, if an authorization workflow already exists:

`Review Budget Extension`

Do not automatically increase the budget.

Avoid:

- "guaranteed"
- "free money"
- "AI-powered"
- flashy animations
- generic AI dashboard copy

## 14. Deterministic Demo Scenario

Use a deterministic synthetic portfolio that is actually solved by the existing optimizer.

Illustrative target:

- Budget = ₹10
- Several positive-ENR candidate actions exist
- Current budget selects the best feasible allocation
- A budget relaxation of ₹2 or ₹10 changes the optimal portfolio
- The system reports the actual objective delta

Example interpretation:

> Budget ₹10 → expected net recovery ₹X  
> Budget ₹12 → expected net recovery ₹Y  
> Incremental expected net recovery = ₹(Y-X)  
> Discrete marginal budget value = `(Y-X) / ₹2`

**Important:** the final demo numbers must be generated by the real optimizer, not hardcoded merely because they look persuasive.

## 15. Paise Precision

Use the repository's existing integer-paise representation wherever possible.

For financial calculations:

- avoid binary floating-point for money;
- use `Decimal` where the repository's conventions require decimal arithmetic;
- round only at presentation boundaries;
- preserve enough internal precision for ratios;
- never compare monetary values after lossy formatting.

## 16. Edge Cases

The implementation must handle:

1. All positive-ENR opportunities already fit within the budget.  
   - Marginal value = 0 for the tested increment.
2. Relaxing the budget produces no portfolio change.  
   - Incremental expected net recovery = 0.
3. Budget = 0.
4. Very large budget.
5. Budget increment smaller than every incremental feasible upgrade.
6. Multiple candidates with equivalent values.
7. Candidates whose action cost exceeds the available budget.
8. Negative-ENR actions.
9. `NO_ACTION` / non-intervention states.
10. Integer paise precision.
11. Optimizer timeout/failure during the secondary calculation.

## 17. Failure Modes

The secondary shadow-price calculation must not take down the primary allocation.

If the secondary solve exceeds a configured latency threshold:

- return the normal portfolio decision;
- return shadow-price metrics as unavailable;
- emit an observable diagnostic.

Do not silently substitute fabricated or stale values.

## 18. Test Plan

Add focused tests for:

### Core
- Known budget relaxation produces the expected portfolio objective delta.
- Marginal value equals `ΔENR / ΔBudget`.

### Zero case
- Additional budget does not change the optimum → marginal value is zero.

### Discrete behavior
- A small increment that unlocks nothing returns zero.
- A larger increment that changes the allocation returns the correct delta.

### Determinism
- Same inputs produce identical metrics.

### Precision
- Paise-level calculations remain exact under repository conventions.

### Regression
- Existing portfolio optimizer tests continue to pass.
- Existing economic tests continue to pass.
- Full test suite remains green.

## 19. Security / Authorization

Shadow Price is informational.

It must not:

- modify merchant budget limits automatically;
- execute rejected actions;
- bypass policy;
- bypass authentication/RBAC;
- create payment links;
- retry payments;
- bypass webhook validation.

If the existing product already supports a budget-change workflow, the UI may link to that authorized workflow.

Do not introduce a new budget-modification endpoint solely for this feature unless required by the actual application.

## 20. Observability / Audit

Record enough information to explain a displayed metric:

- current budget
- comparison budget / increment
- base objective
- relaxed objective
- incremental objective
- calculation status
- timestamp
- model/optimizer version where already available

The audit trail should make the result reproducible.

## 21. Architecture

Preserve:

> **ML predicts. Economics values. Policy controls. Executor acts.**

Shadow Price belongs in the economics/portfolio layer.

Conceptually:

```text
Payment Context
      |
      v
Action-Conditioned ML
      |
      v
ENR / Economics
      |
      v
Portfolio Optimizer
      |
      +----> Base Allocation
      |
      +----> Discrete Marginal Budget Value
      |
      v
Policy / Authorized Budget Workflow
      |
      v
Executor
```

The Shadow Price evaluator must not become an execution actor.

## 22. What This Feature Must NOT Do

- Do not automatically increase the merchant budget.
- Do not execute rejected actions.
- Do not alter the base portfolio allocation merely to produce the metric.
- Do not describe expected recovery as guaranteed.
- Do not claim a true continuous Lagrange multiplier unless mathematically demonstrated.
- Do not introduce a new ML model.
- Do not introduce an LLM.
- Do not redesign the portfolio optimizer.

## 23. Feature Flag / Rollback

If the repository uses feature flags, support:

`ENABLE_SHADOW_PRICING`

When disabled:

- primary portfolio behavior remains unchanged;
- API exposes `null`/unavailable shadow-price metrics;
- UI falls back to standard portfolio view.

A configuration mechanism consistent with the existing repository is preferable to adding a new configuration framework.

## 24. Acceptance Criteria

The feature is complete when:

1. It computes the discrete marginal budget value from actual portfolio objective deltas.
2. It is mathematically documented as a discrete measure.
3. The UI presents the economic opportunity accurately.
4. Monetary calculations follow repository precision rules.
5. Secondary calculation failure does not break primary allocation.
6. The execution path remains isolated.
7. Deterministic tests cover positive, zero, and edge cases.
8. Existing tests remain passing.
9. Documentation clearly distinguishes tested behavior from synthetic/demo assumptions.

## 25. Why This Matters to RevPilot

The portfolio optimizer answers:

> **"Where should I spend my ₹50?"**

Shadow Price adds:

> **"What is the expected economic value of relaxing my ₹50 constraint?"**

That creates a new meta-economic decision dimension: the system evaluates not only the portfolio, but the **economic cost of the portfolio constraint itself**.

This is the intended conceptual extension—not a generic "AI insight" feature.

# Strategic Positioning

Use the term **Discrete Marginal Budget Value** in technical documentation.

In the pitch/UI, a shorter label such as **Marginal Budget Value** is acceptable.

The one-sentence explanation:

> **RevPilot not only allocates scarce recovery budget; it can quantify what additional recovery value that constraint is preventing.**
