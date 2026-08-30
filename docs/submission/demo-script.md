# RevPilot 5-Minute Pitch Script

### [0:00 - 0:30] The Problem
**Visual:** Slide showing a $10 payment failing, and a generic system sending 3 SMS messages costing $3 to recover it.
**Script:** "Every payment gateway offers retries. But generic retries have a fatal flaw: they optimize for gross conversion, ignoring the cost of recovery. They will happily spend ₹50 in SMS fees and brand friction to chase a ₹100 payment that the customer was never going to complete anyway. Revenue at risk is not the same as revenue worth chasing. Enter RevPilot."

### [0:30 - 1:15] Real Case (Product Demo)
**Visual:** Open RevPilot Dashboard side-by-side with the Terminal. Inject a ₹50,000 High-Value case and a ₹5 Low-Value case.
**Script:** "RevPilot is an autonomous, post-abandonment recovery engine. Let's look at two failed payments that just hit our webhook. One is a high-value ₹50k transaction from an established customer. The other is a ₹5 transaction failing for insufficient funds."

### [1:15 - 2:00] ML Probabilities
**Visual:** Show the Terminal output / Dashboard displaying the Action-Conditioned ML Probabilities.
**Script:** "Instead of static rules, RevPilot passes the context and candidate actions to our LightGBM Machine Learning model. The model calculates the exact probability of recovery *conditioned on the action we take*. For the ₹50k case, sending a Payment Link has a 71.3% probability of success. Retrying silently only has 58%."

### [2:00 - 2:40] Economic Ranking
**Visual:** Highlight the Expected Net Return (ENR) column.
**Script:** "But probabilities aren't enough. Our deterministic Economic Engine maps these probabilities against the merchant's financial policy. For the ₹50k case, a 71.3% probability yields a massive Expected Value, easily covering the ₹2.50 cost. It executes the Payment Link. But look at the ₹5 case. Even though the model predicts a 71% success rate, the Expected Value is just ₹3.55. The SMS costs ₹2.50, and the brand friction is ₹5.00. The Net Return is deeply negative. RevPilot intelligently halts, saving the merchant money."

### [2:40 - 3:30] Real Razorpay Execution & Webhooks
**Visual:** Open Razorpay Test Dashboard. Click the Payment Link. Show the Webhook securely clearing the case in the UI.
**Script:** "This isn't just theory. For the high-value case, RevPilot just created a real Razorpay Payment Link via the API. When the customer pays it, Razorpay fires a webhook. RevPilot validates the HMAC-SHA256 signature, idempotently updates the PostgreSQL state machine, and records the recovered Test Mode payment. No hallucination, just bounded financial execution."

### [3:30 - 4:15] Benchmark & Proof
**Visual:** Show the `batch_eval.py` Net Recovered Revenue benchmark results.
**Script:** "We evaluated this across 500 cases in our synthetic world model. RevPilot mathematically beats a 'Max Retry' strategy on Net Recovered Revenue across every single seed. It does this not by recovering more gross payments, but by intelligently refusing to throw good money after bad. It drops interventions by 15%, increasing net margins."

### [4:15 - 4:40] Architecture
**Visual:** Quick architecture diagram (Predict -> Value -> Policy -> Act).
**Script:** "To pass enterprise security, we enforce strict architectural boundaries. The ML Predictor *only* outputs probabilities. It has no access to Razorpay. The Economic Engine calculates value. The Policy Manager grants permission. The Agent Executor performs the API call. LLMs are intentionally excluded from the execution path to guarantee deterministic financial safety."

### [4:40 - 5:00] Limitations & Close
**Visual:** Summary slide.
**Script:** "This prototype is built on synthetic training data and Razorpay Test Mode. For production, the model requires historical merchant data for calibration. But the boundaries are real, the API integration is real, and the economic math is real. RevPilot doesn't just recover payments—it protects margins."
