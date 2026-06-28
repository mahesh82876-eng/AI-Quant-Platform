# ADR-0006: Risk Engine as non-bypassable enforcement point

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Principal Quant Researcher, Security Engineer
- Related: ADR-0001, ADR-0005

## Context

The charter is explicit: "No trade should bypass the Risk Engine." In a system
with multiple execution paths (live, paper, rebalancing, manual override),
it's easy for a well-meaning engineer to add a shortcut that submits an order
without a risk check. For an institutional trading platform that is
unacceptable — it is the single most dangerous class of bug.

## Options considered

**A. Convention: "always call risk before submitting."** Relies on memory and
code review. Will be violated eventually. Rejected.

**B. Risk check as a recommended helper.** Still bypassable. Rejected.

**C. Risk Engine as the only path to the broker, enforced by architecture and
verified by test (chosen).** The `TradingService` submits orders *only* through
`RiskEngine.guard(order_intent)`, which internally calls `pre_trade_check`
and only forwards to `BrokerPort` on PASS. A dedicated test asserts that no
code path can reach `BrokerPort.submit` without a recorded risk decision.

## Decision

Make the Risk Engine the **sole chokepoint** to any broker. Execution flows:

```
intent → RiskEngine.guard(intent) → [PASS] → BrokerPort.submit
                                 → [REJECT] → audit + notify
```

Every `guard()` call writes an immutable risk decision (allow/deny + reason +
limits evaluated) to the audit/risk log. A repository-level invariant test
fails the build if `BrokerPort` (or any adapter) is referenced outside the
risk-guarded execution path and tests.

## Consequences

**Positive**
- The most dangerous failure mode is structurally impossible, not procedural.
- Full auditability: every order has a risk decision attached.
- Limits are centralized and configurable; changes are reviewed, not scattered.

**Negative**
- Slightly more ceremony to submit an order; acceptable and intended.
- The guard must be fast (pre-trade) — risk limits must be cheap to evaluate.

**Neutral**
- Post-trade risk (VaR/CVaR/drawdown) runs continuously in a worker, separate
  from the synchronous pre-trade check.
