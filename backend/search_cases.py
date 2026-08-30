import asyncio
from app.database.core import SessionLocal
from app.economics.engine import EconomicEngine
from app.models.domain import RevenueRiskCase, CaseStatus

async def search():
    engine = EconomicEngine()
    
    for amount in [10, 15, 20, 22, 25, 28, 30, 35, 40, 50, 60, 75, 100, 150]:
        for history in [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0]:
            for failures in [0, 1, 2, 3, 5, 8]:
                evals = engine.evaluate_case(
                    case_type="failed_payment",
                    amount_at_risk=amount * 100,
                    attempt_count=1,
                    age_days=0,
                    failure_reason="insufficient_funds",
                    customer_history_score=history,
                    recent_30d_failures=failures
                )
                
                if not evals: continue
                
                best = evals[0]
                cpl = next((e for e in evals if e.action_type == 'CREATE_PAYMENT_LINK'), None)
                
                if cpl and best.action_type != 'CREATE_PAYMENT_LINK' and best.action_type != 'NO_ACTION':
                    if best.success_probability < cpl.success_probability:
                        print(f"FOUND MATCH: Amount={amount} INR, History={history}, Failures={failures}")
                        print(f"Winner: {best.action_type} (Prob: {best.success_probability:.4f}, ENR: {best.final_enr})")
                        print(f"CPL: {cpl.action_type} (Prob: {cpl.success_probability:.4f}, ENR: {cpl.final_enr})")
                        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(search())
