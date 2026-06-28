# ADR-0005: Broker abstraction (BrokerPort) — Alpaca first, IBKR later

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Senior Backend Engineer, Principal Quant Researcher
- Related: ADR-0001, ADR-0006, ADR-0007

## Context

Version 1 supports only Alpaca paper trading, but the charter requires that
"adding Interactive Brokers later requires minimal changes." If the codebase
calls Alpaca's SDK directly from strategies or the API layer, introducing IBKR
means rewriting the execution path — exactly the mistake ADR-0001 exists to
prevent. Different brokers also have different order semantics, rate limits,
and lifecycles that must be normalized.

## Options considered

**A. Call the broker SDK directly where needed.** Fastest to write, but
couples the whole system to one broker and makes a swap a multi-phase rewrite.

**B. A thin `BrokerPort` interface with one adapter per broker (chosen).**
The domain, risk engine, and trading service talk to `BrokerPort`. Alpaca is
the first adapter; IBKR will be a second adapter behind the same interface.

**C. A generic third-party broker-abstraction library.** Convenient, but
adds a heavy dependency that lags broker features and hides semantics we must
control (order states, partial fills, reconnection). Rejected.

## Decision

Define a `BrokerPort` (Protocol/ABC) covering: account, buying power,
positions, order submission (market/limit/stop/stop-limit/bracket), order
status, portfolio history, trade history. Implement an `AlpacaBrokerAdapter`
for paper trading first. The broker is selected by configuration; the core
never imports a broker SDK.

## Consequences

**Positive**
- IBKR (or any future broker) is a new adapter — no core changes.
- Strategies and the Risk Engine are broker-agnostic (ADR-0007).
- We can unit-test the trading service with a `FakeBrokerAdapter`.

**Negative**
- The port must be designed carefully up front: too thin and adapters leak
  semantics; too fat and it's broker-shaped. We'll iterate via ADRs as
  real broker behaviors surface in Phase 15.

**Neutral**
- Order normalization (broker states → our `OrderState`) lives in the adapter.
- Live trading (Phase 16) reuses the same port with a live Alpaca adapter.
