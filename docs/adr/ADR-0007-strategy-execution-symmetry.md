# ADR-0007: Strategy/execution symmetry (backtest = live)

- Status: accepted
- Date: 2026-06-28
- Deciders: Principal Quant Researcher, Senior Backend Engineer, CTO
- Related: ADR-0001, ADR-0005, ADR-0011

## Context

A backtest is only a credible precursor to live trading if the *same* strategy
code runs in both. The classic failure is a "backtest strategy" that takes
convenient shortcuts (perfect fill, no latency, peeking at the next bar) and
then must be rewritten for live — at which point the backtest results no longer
describe the live strategy. The charter demands realism and warns against
ignoring costs.

## Options considered

**A. Separate backtest and live strategy APIs.** Lets each be "optimized," but
guarantees divergence and destroys trust in backtests. Rejected.

**B. One `Strategy` interface run by two runtimes that differ only in I/O and
clock (chosen).** A strategy is a pure mapping
`(bars, features, context) -> Optional[Signal]`. The backtest runtime feeds
historical bars via an event loop with a realistic fill model; the live runtime
feeds real-time bars via the broker. Same strategy object, same Risk Engine.

**C. Vectorized-only backtests (no event loop).** Fast, but cannot share a
runtime with live and hides latency/order-book effects. Used internally for
rapid research, but the *validated* backtest is event-driven for parity.

## Decision

Define a single `Strategy` protocol. Provide two runtimes — `BacktestRuntime`
(event loop + cost-aware fill model) and `LiveRuntime` (broker-fed) — that
present the same interface to the strategy. The Risk Engine is identical in
both. Costs are mandatory in the backtest fill model (ADR-0011).

## Consequences

**Positive**
- A validated backtest is a genuine predictor of live behavior.
- Strategy code is written once and runs everywhere.
- Bug fixes to a strategy apply to both contexts simultaneously.

**Negative**
- The runtime must faithfully simulate broker behavior; we invest in a
  realistic fill model (slippage, partial fills, rejection) from day one.
- Pure vectorized research backtests are a *separate* fast-path, clearly
  labeled as non-validated, to avoid confusion.

**Neutral**
- The shared runtime contract is owned by the backtesting context (Phase 11).
