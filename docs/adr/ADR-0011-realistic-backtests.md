# ADR-0011: Realistic backtests (commission + slippage + latency)

- Status: accepted
- Date: 2026-06-28
- Deciders: Principal Quant Researcher, CTO, Senior Backend Engineer
- Related: ADR-0007

## Context

The charter lists "Don't ignore transaction costs / slippage / commissions"
among the mistakes to never repeat. A backtest without costs is fantasy: it
overstates returns, favors high-turnover strategies, and erodes trust when the
strategy goes live and underperforms. Realism must be the default, not an option.

## Options considered

**A. Optional costs, off by default for "cleaner" equity curves.** Rejected —
this is precisely the anti-pattern the charter bans.

**B. Costs modeled, but easily zeroed out.** Tempting; still a footgun.

**C. Cost-aware fill model as the only fill model; costs are required inputs
with sane per-asset defaults (chosen).** Commission (per-share or
percent/notional), slippage (basis points or model-based), and a latency
assumption (next-bar or modeled) are mandatory. A backtest with zero costs
must be an explicit, logged, "idealized" configuration — never the silent
default.

## Decision

The backtesting fill model requires a `CostModel` (commission + slippage) and
a `LatencyModel`. Defaults are realistic per asset class. Configuring all costs
to zero is allowed only via an explicit `idealized=True` flag that is logged
prominently. Walk-forward testing (in-sample train / out-of-sample test) is a
first-class harness, not an afterthought.

## Consequences

**Positive**
- Backtest credibility is high; live results track backtests (ADR-0007).
- High-turnover strategies are penalized honestly.

**Negative**
- Equity curves look "worse" than naive backtests — this is a feature.
- Cost models need calibration to real broker fills over time.

**Neutral**
- The fill model is property-tested against analytic expectations
  (e.g., cost = f(qty, price, model) for simple cases).
