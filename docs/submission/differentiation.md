# Product Differentiation

A common evaluator question: *"Doesn't Razorpay already do this?"*

The short answer is **no**. RevPilot operates in a fundamentally different part of the payment lifecycle and optimizes for a completely different mathematical objective.

## 1. RevPilot vs. Razorpay In-Checkout Retries
**Razorpay Native Checkouts** automatically prompt users to retry immediately upon a failed payment, often within the same session. 
* **The Gap:** If the user abandons the session entirely (e.g., they close the tab, their session expires, or they walk away), the synchronous checkout retry cannot reach them.
* **RevPilot's Role:** RevPilot is an **asynchronous post-abandonment** engine. It wakes up hours or days after the abandonment, computes the exact Expected Net Return of pursuing the customer, and orchestrates async channels (Payment Links via SMS/Email) if mathematically viable. 

## 2. RevPilot vs. Razorpay Optimizer / Smart Routing
**Razorpay Optimizer** prevents failures *before or during* the transaction by dynamically routing the payment attempt to the Gateway or Acquirer with the highest real-time success rate.
* **The Gap:** Optimizer works on the plumbing layer. If the failure is user-driven (e.g., Insufficient Funds, Abandonment, Cancelled by User), routing rules cannot fix it.
* **RevPilot's Role:** RevPilot acts *after* the terminal failure has been recorded by the gateway. It handles the *human/user* recovery layer, rather than the *technical routing* layer.

## 3. RevPilot vs. Generic Dunning Systems
Traditional dunning systems (e.g., Stripe Billing retries, Chargebee) use static, rule-based schedules (e.g., "Retry on Day 1, Day 3, Day 7").
* **The Gap:** They treat all $50 transactions the same, regardless of the customer's historical standing, the explicit reason for failure, or the cost of the intervention. They optimize blindly for *Gross Recovery*.
* **RevPilot's Role:** RevPilot dynamically predicts $P(recovery)$ conditioned on the specific *action* (e.g. Email vs SMS Link) and executes only if the Expected Net Return (ENR) exceeds the financial and reputational friction costs. It protects merchants from spending ₹10 to chase a low-probability ₹5 transaction.

## 4. Why Not Razorpay Agent Studio?
Razorpay Agent Studio provides the components to build generative AI support workflows. 
* **RevPilot's Role:** RevPilot is not a chat bot. It does not use LLMs to guess at recovery. It uses tabular/temporal Machine Learning (LightGBM) because predicting precise financial probability requires deterministic, causally-structured models, not generative text. RevPilot's strict `Predict -> Value -> Policy -> Act` bounded architecture enforces financial safety that free-form LLM agents cannot.
