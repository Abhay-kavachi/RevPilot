# Decision Utility Methodology

## 1. Regret Formulation

We measure model performance not just via predictive accuracy (AUC/Brier), but directly through Financial Utility.

Regret = Oracle Utility - Strategy Utility

- **Oracle Utility**: The theoretical max utility if we knew the potential outcomes of all actions and picked the highest net value.
- **Strategy Utility**: The utility achieved by the ML policy selecting the action with the highest Expected Value based on its predicted probabilities.

## 2. Potential Outcomes Evaluator

The World Model generates Y(wait), Y(email), Y(sms), Y(whatsapp), Y(link), and Y(retry) secretly for all cases. 
The ML model scores all candidate actions, picks the best EV action, and the Evaluator checks the corresponding hidden potential outcome to compute the realized utility.