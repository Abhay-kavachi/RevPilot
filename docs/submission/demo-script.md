# RevPilot 5-Minute Pitch Script

### [0:00 - 0:30] The Problem
**Visual:** Slide showing a $10 payment failing, and a generic system sending 3 SMS messages costing $3 to recover it.
**Script:** "Every payment gateway offers retries. Generic retry logic can optimize recovery attempts without explicitly pricing the economic cost of the next intervention. They will happily spend 50 INR in SMS fees and brand friction to chase a 100 INR payment that the customer was never going to complete anyway. Revenue at risk is not the same as revenue worth chasing. Enter RevPilot."

### [0:30 - 1:15] Real Case (Product Demo)
**Visual:** Open RevPilot Dashboard side-by-side with the Terminal. Inject a high-value 50,000 INR case, a marginal 28 INR case, and a low-value 5 INR case.
**Script:** "RevPilot is an autonomous, post-abandonment recovery engine. Let's look at three failed payments that just hit our webhook. One is a 50,000 INR transaction from an established customer, one is a marginal 28 INR transaction, and one is a 5 INR transaction failing for insufficient funds. Why didn't RevPilot just retry all of them? Because the expected net return wasn't there."

### [1:15 - 2:00] ML Probabilities
**Visual:** Show the Terminal output / Dashboard displaying the Action-Conditioned ML Probabilities.
**Script:** "Instead of static rules, RevPilot passes the context and candidate actions to our LightGBM Machine Learning model. The model calculates the exact probability of recovery *conditioned on the action we take*. For the 50,000 INR case, sending a Payment Link has a 71.3% probability of success. Retrying silently only has 58%."

### [2:00 - 2:40] Economic Ranking
**Visual:** Highlight the Expected Net Return (ENR) column.
**Script:** "But probabilities aren't enough. Our deterministic Economic Engine maps these probabilities against the merchant's financial policy. For the 50,000 INR case, a 71.3% probability yields a massive Expected Value, easily covering the 2.50 INR cost. It executes the Payment Link. But look at the 28 INR case. A Payment Link has a high 73.6% success rate, yielding a net return of 13.10 INR. But a simple Reminder has a much lower 56% success rate, yet its costs are so low that it yields a higher net return of 13.20 INR. RevPilot intelligently down-selects to the cheaper action. And for the 5 INR case? RevPilot also knows when the economically correct recovery action is no action."

### [2:40 - 3:30] Real Razorpay Execution & Webhooks
**Visual:** Open Razorpay Test Dashboard. Click the Payment Link. Show the Webhook securely clearing the case in the UI.
**Script:** "This isn't just theory. For the high-value case, RevPilot just created a real Razorpay Payment Link via the API. When the customer pays it, Razorpay fires a webhook. RevPilot validates the HMAC-SHA256 signature, idempotently updates the PostgreSQL state machine, and records the recovered Test Mode payment. No hallucination, just bounded financial execution."

### [3:30 - 4:15] Benchmark & Proof
**Visual:** Show the `batch_eval.py` Net Recovered Revenue benchmark results.
**Script:** "We evaluated this across 500 cases in our synthetic world model. RevPilot mathematically beats a 'Max Retry' strategy on Net Recovered Revenue across every single seed. It does this not by recovering more gross payments, but by intelligently refusing to throw good money after bad. It drops interventions by 15%, increasing net margins."

### [4:15 - 4:45] The 11/10 Portfolio Feature
**Visual:** Run `python scripts/run_portfolio.py` in the terminal to show the capital allocation downgrade in action.
**Script:** "But we didn't stop at case-by-case decisions. We realized recovery is a capital allocation problem. Given a fixed merchant budget, RevPilot's optional Portfolio Optimizer looks across the entire batch. If budget is tight, it solves a dynamic programming knapsack problem to intentionally *downgrade* actions on mid-value cases—like sending a 50 INR reminder instead of a 250 INR link—just to fund the highest-yield interventions elsewhere. It maximizes global ROI for every dollar spent."

### [4:45 - 5:10] Architecture
**Visual:** Quick architecture diagram (Predict -> Value -> Policy -> Act).
**Script:** "To pass enterprise security, we enforce strict architectural boundaries. The ML Predictor *only* outputs probabilities. It has no access to Razorpay. The Economic Engine calculates value. The Policy Manager grants permission. The Agent Executor performs the API call. LLMs are intentionally excluded from the execution path to enforce deterministic financial safety."

### [5:10 - 5:30] Limitations & Close
**Visual:** Summary slide.
**Script:** "Within the tested failure/concurrency scenarios, this prototype is built on synthetic training data and Razorpay Test Mode. For production, the model requires historical merchant data for calibration. But the boundaries are real, the API integration is real, and the economic math is real. RevPilot doesn't just recover payments—it protects margins."
