# Shopee AI On-Call Agent - ShopOps

**An AI-powered operations agent that proactively detects, diagnoses, and resolves business-critical issues for Shopee sellers via Telegram.**

The current clients are a standalone shop browser app and a separate Telegram-style mobile orchestrator chat app. A presentation-only viewer can display both independent apps in one tab. See [client setup and service boundaries](docs/client-workspace.md) and [feature development patterns](docs/feature-development.md).

## 1. Problem

Shopee sellers manually monitor daily operations through Seller Center. While the platform provides operational data, sellers still need to identify problems, determine root causes, and take corrective actions themselves.

This reactive workflow leads to delayed responses, profit leakage, operational inefficiencies, and account-health risks.

## 2. Target Users

- **Primary:** Small and medium Shopee sellers in Vietnam, processing 20–500 orders/day with teams of 1–5 people and limited operational or analytical resources.
- **Secondary:** E-commerce agencies managing multiple Shopee shops.

## 3. Solution

A **Telegram-first AI operations agent** that continuously monitors shop performance, identifies actionable issues, recommends solutions, executes seller-approved actions, and verifies outcomes.

**Core Loop: Detect → Classify → Plan → Approve → Execute → Verify → Learn**

### 1. Detect — Proactive Monitoring
Continuously analyze shop data to detect operational and financial anomalies:

- **Customer Experience:** Negative review spikes, recurring complaints, increasing return rates.
- **Profitability:** Loss-making vouchers, abnormal fees, payout discrepancies.
- **Account Health:** Penalty points, cancellation spikes, late-shipment and SLA risks.
- **Inventory:** Low-stock or out-of-stock products with high demand.

### 2. Classify — Root-Cause Analysis
Correlate related signals into a single actionable incident.

Each incident includes:
- Issue summary and probable root cause.
- Supporting evidence and affected products/orders.
- Severity, urgency, and estimated business impact.

*Example: Multiple complaints about tight-fitting shirts → "Product sizing runs small."*

### 3. Plan — Action Recommendations
Generate 2–3 actionable recommendations delivered through Telegram.

Each recommendation specifies:
- Expected impact and estimated cost.
- Potential risks and reversibility.
- Required permissions and execution scope.

### 4. Approve — Human-in-the-Loop
Sellers review recommendations and approve, reject, or modify actions directly through Telegram.

### 5. Execute — Controlled Automation
Execute approved actions using Shopee APIs or a mock server, subject to integration capabilities and permissions.

Maintain execution logs, enforce safety checks, and support rollback where technically feasible.

### 6. Verify — Outcome Monitoring
Automatically track predefined success metrics after execution.

Compare outcomes against baseline performance to determine whether the action resolved the issue or requires further intervention.

### 7. Learn — Progressive Autonomy
Adapt recommendations and automation permissions using historical outcomes, seller feedback, and demonstrated reliability.

**Trust Levels:**
1. **Advisory:** Recommend actions; require seller approval.
2. **Supervised Automation:** Auto-execute approved action types with notifications and rollback when available.
3. **Autonomous:** Execute low-risk, pre-authorized actions without requiring individual approval or routine notifications.

## 4. Value Proposition

**From reactive dashboards to proactive, closed-loop operations.**

- **Prevent Profit Leakage:** Detect financial losses and operational anomalies early.
- **Protect Account Health:** Identify compliance, fulfillment, and penalty risks before escalation.
- **Reduce Manual Work:** Automate monitoring, diagnosis, and repetitive operational tasks.
- **Accelerate Decision-Making:** Deliver evidence-based recommendations through Telegram.
- **Build Trustworthy Automation:** Increase autonomy gradually through measurable results and seller-defined controls.

## 5. Key Differentiator

Unlike traditional dashboards and alerting tools, the Shopee AI On-Call Agent provides **end-to-end incident management**:

**Monitoring → Diagnosis → Decision Support → Execution → Outcome Verification → Continuous Improvement**

The goal is not merely to notify sellers when something goes wrong, but to **help resolve the issue, verify the result, and progressively automate recurring decisions.**
