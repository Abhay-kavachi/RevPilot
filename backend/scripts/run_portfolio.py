import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.economics.engine import EconomicEngine
from app.economics.portfolio import RecoveryPortfolioOptimizer

def print_portfolio(result, budget_paise):
    print("=========================================================================================")
    print("SYNTHETIC PORTFOLIO BENCHMARK (MERCHANT CAPITAL ALLOCATION)")
    print("=========================================================================================")
    print(f"Recovery Budget       : {budget_paise / 100:,.2f} INR")
    print(f"Selected Actions      : {len(result.selected_actions)}")
    print(f"Skipped Opportunities : {len(result.skipped_cases)}")
    print(f"Budget Utilized       : {result.total_spend / 100:,.2f} INR")
    print(f"Expected Net Recovery : {result.expected_net_recovery / 100:,.2f} INR")
    print(f"Net Recovery / 1 INR  : {(result.expected_net_recovery / result.total_spend) if result.total_spend else 0:,.2f} INR")
    print("-" * 89)
    print(f"{'Case ID':<15} | {'Action':<22} | {'Prob':<6} | {'Cost':<5} | {'ENR (Paise)'}")
    print("-" * 89)
    for item in result.selected_actions:
        action = item["action"]
        prob = f"{action.success_probability:.4f}"
        print(f"{item['case_id']:<15} | {action.action_type:<22} | {prob:<6} | {action.cost:<5} | {action.final_enr}")
    print("\nSkipped Cases:")
    for case_id in result.skipped_cases:
        print(f"- {case_id} (Skipped due to negative ENR or budget constraints)")
    print("=========================================================================================\n")


def main():
    engine = EconomicEngine()
    cases_dict = {}

    # Case 1: High Value (50k INR), Loyal, No failures. Very profitable.
    # Unconstrained optimal: CREATE_PAYMENT_LINK (Cost 250, Friction 500)
    cases_dict["case_high_value"] = engine.evaluate_case(
        "failed_payment", 5000000, 0, 0, "insufficient_funds", 1.0, 0
    )

    # Case 2: Marginal Value (28 INR), High Risk, 1 failure.
    # Unconstrained optimal: SEND_REMINDER (Cost 50, Friction 200)
    cases_dict["case_marginal"] = engine.evaluate_case(
        "failed_payment", 2800, 1, 0, "insufficient_funds", 0.0, 1
    )

    # Case 3: High Probability but Expensive (e.g. 5,000 INR Support Esc) vs Cheaper Option
    # Let's say a 1500 INR case, where Support is cost 5000 (negative ENR), Link is cost 250, Reminder is cost 50.
    cases_dict["case_mid_value"] = engine.evaluate_case(
        "failed_payment", 150000, 1, 0, "insufficient_funds", 0.5, 0
    )
    
    # Case 4: Negative Yield (5 INR) -> ALWAYS skipped
    cases_dict["case_negative"] = engine.evaluate_case(
        "failed_payment", 500, 2, 0, "insufficient_funds", 0.0, 3
    )

    # Case 5: Another attractive case that might get skipped if budget is strictly limited
    cases_dict["case_attractive_but_skipped"] = engine.evaluate_case(
        "failed_payment", 45000, 1, 0, "insufficient_funds", 0.8, 0
    )

    print("\n[Unconstrained Case-by-Case Analysis]")
    total_unconstrained_spend = 0
    total_unconstrained_enr = 0
    for cid, evals in cases_dict.items():
        best = evals[0]
        if best.final_enr > 0:
            print(f"- {cid}: Optimal action is {best.action_type} (Cost: {best.cost} paise, Yield: {best.final_enr:,} paise)")
            total_unconstrained_spend += best.cost
            total_unconstrained_enr += best.final_enr
        else:
            print(f"- {cid}: All actions yield negative ENR. Will stop naturally.")

    print(f"Total Optimal Unconstrained Spend: {total_unconstrained_spend} paise")
    
    # Restrict budget to severely constrain choices
    # Let's say the optimal spend is roughly 250 + 50 + 250 + 50 = 600 paise.
    # We will limit the budget to 300 paise. This forces the engine to skip the 'attractive_but_skipped' case
    # or downgrade an action to save budget for something with a higher ENR/cost ratio.
    budget_paise = 300 
    
    optimizer = RecoveryPortfolioOptimizer()
    result = optimizer.optimize(cases_dict, budget_paise)
    
    print()
    print_portfolio(result, budget_paise)

if __name__ == "__main__":
    main()
