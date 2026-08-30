import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from app.database.core import Base, engine as db_engine, get_db
from app.models.domain import RevenueRiskCase, CaseStatus, CaseDecision, AuditEvent
from app.economics.engine import EconomicEngine

def print_evaluation(title, context, evaluations):
    print(f"\n==========================================================================================")
    print(f"{title}")
    print(f"==========================================================================================")
    print(f"Context: {context}")
    print("-" * 90)
    print(f"{'Action':<25} | {'Prob':<6} | {'EV (Paise)':<12} | {'Cost':<6} | {'Frict':<6} | {'ENR (Paise)':<12}")
    print("-" * 90)
    
    for ev in evaluations:
        prob_str = f"{ev.success_probability:.4f}"
        print(f"{ev.action_type:<25} | {prob_str:<6} | {ev.expected_value:<12} | {ev.cost:<6} | {ev.friction:<6} | {ev.final_enr:<12}")
        
    best_action = evaluations[0]
    print("-" * 90)
    print(f"FINAL DECISION: {best_action.action_type} (ENR: {best_action.final_enr})")
    print(f"PROBABILITY SOURCE: {best_action.probability_source}")
    print("==========================================================================================\n")

def process_case(db, case, title, context, history_score, recent_failures):
    engine = EconomicEngine()
    evals = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=case.amount_at_risk,
        attempt_count=case.attempt_count,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=history_score,
        recent_30d_failures=recent_failures
    )
    
    print_evaluation(title, context, evals)
    best_action = evals[0]
    
    for idx, ev in enumerate(evals):
        decision = CaseDecision(
            id=str(uuid.uuid4()),
            case_id=case.id,
            action_type=ev.action_type,
            expected_value=ev.expected_value,
            success_probability=ev.success_probability,
            cost=ev.cost,
            friction=ev.friction,
            risk=ev.risk,
            final_enr=ev.final_enr,
            is_selected=(idx == 0),
            metadata_blob={
                "source": ev.probability_source,
                "provenance": getattr(ev, 'provenance', {}),
                "rank": idx + 1
            }
        )
        db.add(decision)
    
    case.transition_to(CaseStatus.ASSESSING)
    db.add(AuditEvent(
        case_id=case.id,
        event_type="DECISION_MADE",
        description=f"Action {best_action.action_type} chosen (ENR: {best_action.final_enr})",
        metadata_blob={"enr": best_action.final_enr, "source": best_action.probability_source}
    ))
    db.commit()


def main():
    print("\n[RevPilot] Clearing database and setting up demo fixtures...")
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)
    db = next(get_db())

    # CASE A: High Value Case
    case_A = RevenueRiskCase(
        id="case_high_value",
        merchant_id="merchant_demo",
        customer_id="cust_A",
        case_type="failed_payment",
        amount_at_risk=5000000,  # ₹50,000
        amount_recovered=0,
        status=CaseStatus.OPEN,
        attempt_count=0
    )
    db.add(case_A)

    # CASE B: Low Value Case
    case_B = RevenueRiskCase(
        id="case_low_value",
        merchant_id="merchant_demo",
        customer_id="cust_B",
        case_type="failed_payment",
        amount_at_risk=2800,  # ₹28
        amount_recovered=0,
        status=CaseStatus.OPEN,
        attempt_count=1
    )
    db.add(case_B)
    
    db.commit()

    print("\n[RevPilot] Running ML Predictor & Economic Engine...\n")
    process_case(db, case_A, "CASE A: HIGH VALUE RECOVERY", "Amount = 50,000 INR | Loyal | Recent Failures = 0", history_score=1.0, recent_failures=0)
    process_case(db, case_B, "CASE B: MARGINAL VALUE (Probability vs Cost)", "Amount = 28 INR | High Risk | Recent Failures = 1", history_score=0.0, recent_failures=1)

    print("\n[RevPilot] Demo setup complete. Cases and Decisions are now visible in the Dashboard.")

if __name__ == "__main__":
    main()
