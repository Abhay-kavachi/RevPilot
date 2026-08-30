# RevPilot Benchmark Summary

**Important: SYNTHETIC BENCHMARK** 
*This benchmark measures the structural advantage of the Economic Engine against a naive retry approach. The dataset (`v1.0 Synthetic World Model`) creates chronological failure scenarios with mathematically consistent causal recovery rates. The metric "Net Recovered Revenue (INR)" refers to the hypothetical unit currency in the synthetic simulation, not real-world recovered money.*

## The Benchmark Question
Does optimizing for Expected Net Return (ENR) mathematically outperform a strategy that blindly attempts to maximize gross recovery rate (e.g. attempting all bounded retry/reminder paths)?

## Evaluation Setup
- **Dataset:** 5 distinct random seed populations of 100 cases each.
- **Model Version:** LightGBM_Prod_v1.0 (Action-conditioned probabilities).
- **Competitor:** `MAX_RETRY` (Represents typical static logic: unconditionally try to recover the case using cheap paths up to a hard attempt ceiling).
- **RevPilot Engine:** Uses ML to compute `P(recovery)` conditionally per action, and evaluates whether `P(recovery) * Amount - Cost - Friction > 0`. If `<= 0`, it stops.

## Results

Across all 5 independent seed trials, RevPilot mathematically beats `MAX_RETRY` on **Net Recovered Revenue (INR)**.

| Seed | Strategy | Net Rec (INR) | Gross Rec (INR) | Costs/Friction (INR) | Recovery Rate | Avg Interventions |
|------|----------|---------------|-----------------|----------------------|---------------|-------------------|
| **42** | MAX_RETRY | 94,849 | 96,415 | 1,566 | 86.0% | 1.80 |
| | **REVPILOT** | **94,963** | 96,399 | **1,435** | 79.0% | **1.65** |
| **100**| MAX_RETRY | 106,730 | 108,201 | 1,470 | 84.0% | 1.69 |
| | **REVPILOT** | **106,876** | 108,173 | **1,296** | 74.0% | **1.49** |
| **999**| MAX_RETRY | 108,518 | 109,876 | 1,357 | 90.0% | 1.56 |
| | **REVPILOT** | **108,637** | 109,864 | **1,226** | 85.0% | **1.41** |
|**12345**| MAX_RETRY | 138,739 | 140,027 | 1,287 | 94.0% | 1.48 |
| | **REVPILOT** | **138,864** | 140,004 | **1,139** | 82.0% | **1.31** |
|**55555**| MAX_RETRY | 136,469 | 137,888 | 1,418 | 86.0% | 1.63 |
| | **REVPILOT** | **136,550** | 137,864 | **1,313** | 77.0% | **1.51** |

## Conclusion
RevPilot achieves **higher Net Recovered Revenue** by intentionally achieving a *lower* gross recovery rate. 

It accomplishes this by avoiding "Unnecessary Interventions"—it refuses to spend ₹2.50 + ₹5.00 Friction to chase a ₹50 transaction with a low probability of success, whereas `MAX_RETRY` burns money (and merchant reputation) blindly chasing it. 

The benchmark proves the core thesis: **Revenue at risk is not the same as revenue worth chasing.**
