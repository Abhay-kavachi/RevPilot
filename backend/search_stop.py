import asyncio
from app.database.core import SessionLocal
from app.economics.engine import EconomicEngine
from app.models.domain import RevenueRiskCase, CaseStatus

async def search_stop():
    engine = EconomicEngine()
    
    for amount in [5, 8, 10, 15, 20]:
        for history in [0.0, 0.1, 0.2]:
            for failures in [2, 3, 4, 5]:
                evals = engine.evaluate_case(
                    case_type="failed_payment",
                    amount_at_risk=amount * 100,
                    attempt_count=2,
                    age_days=0,
                    failure_reason="insufficient_funds",
                    customer_history_score=history,
                    recent_30d_failures=failures
                )
                
                if not evals: continue
                best = evals[0]
                
                if best.action_type == 'NO_ACTION':
                    print(f"STOP MATCH: Amount={amount} INR, History={history}, Failures={failures}")
                    for e in evals:
                        print(f"  {e.action_type}: Prob={e.success_probability:.4f}, Cost={e.cost_estimate}, ENR={e.final_enr}")
                    print("-" * 40)

if __name__ == "__main__":
    asyncio.run(search_stop())
