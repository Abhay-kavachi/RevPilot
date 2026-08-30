# RevPilot 5-Minute Pitch Script

**Target Duration:** <= 4:50
**Word Count:** ~470 words (Leaves ~80 seconds for visual breathing room and transitions)

### [0:00 - 0:20] Hook
**Visual:** Slide showing a failed payment vs a high recovery cost.
**Script:** "Every payment gateway offers retries. But generic retry logic can optimize recovery attempts without explicitly pricing the economic cost of the next intervention. They will happily spend 50 INR in SMS fees chasing a 100 INR payment that will never convert. Revenue at risk is not the same as revenue worth chasing. Enter RevPilot."

### [0:20 - 1:20] The 28 INR Hero Case
**Visual:** Open RevPilot Dashboard side-by-side with the Terminal. Inject a marginal 28 INR case.
**Script:** "RevPilot is an autonomous, post-abandonment recovery engine. Consider a marginal 28 INR failed payment. Instead of static rules, RevPilot passes the context and candidate actions to our LightGBM Machine Learning model. The model calculates the exact probability of recovery conditioned on the intervention. A Payment Link has a high 73.6% success rate, yielding an expected value that seems attractive. But our deterministic Economic Engine maps this against the merchant's financial policy. A simple Reminder has a much lower 56% success rate, yet its friction and costs are so low it yields a *higher* net return of 13.20 INR. RevPilot intelligently down-selects to the cheaper action. Higher probability does not equal higher economic value."

### [1:20 - 1:45] STOP Case
**Visual:** Inject a low-value 5 INR case into the Dashboard.
**Script:** "And what about a 5 INR case? Because the friction and transaction costs outweigh the expected value of even the cheapest intervention, every action yields a negative expected net return. RevPilot also knows when the economically correct recovery action is no action. It immediately stops."

### [1:45 - 2:45] Real Razorpay Integration
**Visual:** Inject a 50,000 INR case, open Razorpay Test Dashboard. Click the generated Payment Link. Show the Webhook clearing the case in the UI.
**Script:** "This isn't just theory. For a high-value 50,000 INR case, the expected value easily absorbs the friction, so RevPilot executes the high-probability Payment Link. It creates a real Razorpay Payment Link via the API. When the customer pays it, Razorpay fires a webhook. RevPilot validates the HMAC-SHA256 signature, idempotently updates the PostgreSQL state machine, and records the recovered Test Mode payment. No hallucination, just bounded financial execution."

### [2:45 - 3:35] Benchmark
**Visual:** Show the `batch_eval.py` Net Recovered Revenue benchmark results.
**Script:** "We evaluated this across 500 cases in our synthetic world model. RevPilot mathematically beats a 'Max Retry' strategy on Net Recovered Revenue across every single seed. It does this not by recovering more gross payments, but by intelligently refusing to throw good money after bad. It drops interventions by 15%, cleanly increasing net margins."

### [3:35 - 4:00] Architecture
**Visual:** Quick architecture diagram (Predict -> Value -> Policy -> Act).
**Script:** "To pass enterprise security, we enforce strict architectural boundaries. The ML Predictor *only* outputs probabilities. It has no access to Razorpay. The Economic Engine calculates value. The Agent Executor performs the API call. LLMs are intentionally excluded from the execution path to enforce deterministic financial safety."

### [4:00 - 4:25] Portfolio Optimizer
**Visual:** Run `python scripts/run_portfolio.py` displaying the SYNTHETIC PORTFOLIO BENCHMARK.
**Script:** "Then we realized recovery is also a capital-allocation problem. Given a fixed merchant recovery budget, RevPilot allocates intervention spend across the queue to maximize total expected net recovery. If budget is tight, it can natively downgrade a mid-value intervention just to fund a high-yield opportunity elsewhere, maximizing expected net recovery per rupee spent."

### [4:25 - 4:45] Engineering Tradeoffs
**Visual:** Slide listing "Engineering Decisions: Determinism over Generative Text."
**Script:** "We prioritized deterministic outcomes. We use PostgreSQL `FOR UPDATE SKIP LOCKED` to ensure webhook deduplication, and lightweight tree models because precise financial probability requires causally-structured math, not generative text."

### [4:45 - 5:00] Close
**Visual:** Summary slide.
**Script:** "Within the tested failure scenarios, this prototype is built on synthetic training data and Razorpay Test Mode. For production, the model requires historical merchant data for calibration. But the boundaries are real, the API integration is real, and the economic math is real. RevPilot doesn't just recover payments—it protects margins."
