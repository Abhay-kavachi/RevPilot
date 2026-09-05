from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from app.core.policy import policy_manager

from app.economics.ml_predictor import ml_predictor

class ActionEvaluation(BaseModel):
    action_type: str
    expected_value: int
    success_probability: float
    cost: int
    friction: int
    risk: int
    final_enr: int
    probability_source: str
    provenance: Dict[str, Any] = Field(default_factory=dict)
    guardrail_applied: bool = False
    guardrail_reason: Optional[str] = None

class EconomicEngine:
    """
    Evaluates potential actions using expected value (ENR) calculations, driven by policy and ML probabilities.
    """
    def __init__(self):
        self.policy = policy_manager.economic_policy
        self.recovery = policy_manager.recovery_policy

    def evaluate_case(self, case_type: str, amount_at_risk: int, attempt_count: int, age_days: int = 0, failure_reason: Optional[str] = None, customer_history_score: float = 1.0, recent_30d_failures: int = 0) -> List[ActionEvaluation]:
        if not (0.0 <= customer_history_score <= 1.0):
            raise ValueError(f"customer_history_score must be between 0 and 1, got {customer_history_score}")
            
        evaluations = []
        age_hours = age_days * 24.0
        
        for action in self.recovery.allowed_actions:
            if action == "CLOSE_CASE" or action == "NO_ACTION":
                evaluations.append(ActionEvaluation(
                    action_type=action, expected_value=0, success_probability=0.0, cost=0, friction=0, risk=0, final_enr=0, probability_source="DETERMINISTIC", provenance={}
                ))
                continue
                
            # 1. Fetch base configs from policy
            cost = self.policy.action_costs_paise.get(action)
            friction = self.policy.action_frictions_paise.get(action)
            risk = self.policy.action_risks_paise.get(action)
            
            if cost is None or friction is None or risk is None:
                raise KeyError(f"Missing monetary configuration for action {action}")
            
            provenance = {}
            # 2. Predict success probability
            if ml_predictor is not None and ml_predictor.available:
                # ML Probabilistic Engine
                pred_result = ml_predictor.predict_recovery(
                    amount_at_risk_paise=amount_at_risk,
                    age_hours=age_hours,
                    recent_30d_failures=recent_30d_failures,
                    attempt_count=attempt_count,
                    action=action,
                    horizon="72h"
                )
                p_success = pred_result.probability
                prob_source = pred_result.source
                provenance = {
                    "model_version": pred_result.model_version,
                    "feature_schema_version": pred_result.feature_schema_version,
                    "calibration_version": pred_result.calibration_version,
                    "dataset_version": pred_result.dataset_version,
                    "world_model_version": pred_result.world_model_version,
                    "horizon": pred_result.horizon
                }
            else:
                # Fallback Heuristic Engine
                base_prob = self.policy.get_base_probability(action)
                reason_factor = self.policy.get_failure_reason_multiplier(failure_reason or "unknown")
                attempt_factor = self.policy.get_attempt_multiplier(attempt_count)
                age_factor = self.policy.get_age_multiplier(age_days)
                history_factor = customer_history_score
                
                p_success = base_prob * reason_factor * attempt_factor * age_factor * history_factor
                prob_source = "POLICY_FALLBACK"
                
            p_success = max(0.0, min(1.0, p_success)) # Technical invariant: Probability bounds
            
            # 3. Calculate Net Expected Value (EV)
            ev = int(amount_at_risk * p_success)
            enr = ev - cost - friction - risk
            
            evaluations.append(ActionEvaluation(
                action_type=action,
                expected_value=ev,
                success_probability=p_success,
                cost=cost,
                friction=friction,
                risk=risk,
                final_enr=enr,
                probability_source=prob_source,
                provenance=provenance
            ))
            
        sorted_evals = sorted(evaluations, key=lambda x: x.final_enr, reverse=True)
        return self._apply_probability_guardrail(sorted_evals)

    def _apply_probability_guardrail(self, evaluations: List[ActionEvaluation]) -> List[ActionEvaluation]:
        """
        Applies the Probability-Preserving Economic Guardrail.
        Re-ranks the evaluations list if a near-optimal economic action has a materially
        higher recovery probability.
        """
        if not evaluations:
            return evaluations
            
        guardrail_config = self.policy.probability_preserving_guardrail
        if not guardrail_config.enabled:
            return evaluations

        # The pure ENR winner is the first element
        a_star = evaluations[0]
        
        # Only operate on actions that have a positive expected net return
        if a_star.final_enr <= 0:
            return evaluations

        enr_max = a_star.final_enr
        
        # Scale-aware effective tolerance
        abs_tol = guardrail_config.minimum_absolute_tolerance_paise
        rel_tol = int(guardrail_config.relative_tolerance * abs(enr_max))
        effective_tolerance = max(abs_tol, rel_tol)
        
        tau_p = guardrail_config.probability_threshold

        # Find the near-optimal set
        a_near = [
            a for a in evaluations
            if a.final_enr > 0 and (enr_max - a.final_enr) <= effective_tolerance
        ]

        if not a_near:
            return evaluations
            
        # Find the candidate with the highest recovery probability within A_near
        # Break ties using final_enr (descending)
        best_candidate = max(a_near, key=lambda a: (a.success_probability, a.final_enr))

        # Check if the best candidate materially beats a_star's probability
        delta_p = best_candidate.success_probability - a_star.success_probability
        
        if best_candidate != a_star and delta_p >= tau_p:
            # Guardrail triggered
            delta_enr = enr_max - best_candidate.final_enr
            best_candidate.guardrail_applied = True
            best_candidate.guardrail_reason = (
                f"Probability Guardrail: Chosen over pure ENR winner ({a_star.action_type}) "
                f"because probability is {delta_p * 100:.1f}pp higher, "
                f"while ENR sacrifice ({delta_enr / 100:.2f} INR) is within "
                f"policy tolerance ({effective_tolerance / 100:.2f} INR)."
            )
            
            # Re-rank: move best_candidate to the front
            new_evals = [best_candidate]
            for a in evaluations:
                if a != best_candidate:
                    new_evals.append(a)
            return new_evals

        return evaluations
