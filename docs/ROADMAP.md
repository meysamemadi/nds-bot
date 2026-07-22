# Roadmap

Each milestone is a separate GitHub Milestone with its own issues. Milestones
are sequential (M2 depends on M1, etc.) but can have contributors working in
parallel once interfaces are agreed (see "Interface contracts" below).

## M0 — Foundations (Week 1)

- [ ] Repo scaffolding, CI skeleton (lint + test on every PR)
- [ ] Data model: candle schema (OHLCV + timestamp), multi-timeframe fetch
      interface (mock data source first, real broker/exchange later)
- [ ] `docs/GLOSSARY.md` populated (symbols: Z, N1, S1, N2, S2, N3, Δ, NSI, α, φ, σₜ...)
- **Owner:** reviews and merges the data schema PR personally — this becomes
  the interface every other module depends on. Get this one right before
  parallelizing.

## M1 — Topology / Node Detection (Weeks 2–3)

Implements: local extremum detection ("6-and-6 test"), swing threshold
filtering, alternating peak/trough validation, Z→N1→S1→N2→S2→N3 sequencing.

- [ ] Local extremum detector (configurable window, not hardcoded to 6)
- [ ] Swing threshold filter (per-asset-class configurable)
- [ ] Alternating candidate builder with replacement rule
- [ ] Full 6-node sequence extraction with structural validation
      (N1>Z, Z<S1<N1, N2>N1, S1<S2<N2, N3>N2)
- [ ] Unit tests using the worked numeric examples in `NDS_SPEC.md` §2
      (same EURUSD example values — if your code doesn't reproduce those
      numbers, it's wrong)

## M2 — Quality Filters (Weeks 3–4)

Implements: NSI, hook ratio, log-scale symmetry checks.

- [ ] Log-return calculator (all displacement math must be on log scale — §1)
- [ ] Hook ratio check (documented: ideal 0.86, spec §3)
- [ ] NSI calculator (documented formula, spec §4) — reproduce the worked
      example (NSI≈0.152 for the healthy cycle, NSI≈1.745 for the bad one)
- [ ] Reversal criteria: slope-sign check (Prop 4.1) and diminishing-swing
      check (Prop 5.2)
- [ ] **Engineering-choice filters are separate and clearly labeled** —
      leg imbalance, third-leg-ratio, or any other filter your team adds
      must live in a clearly separate module/config with a comment
      explaining it is *not* from the spec

## M3 — Trade Levels (Weeks 4–5)

- [ ] Entry/SL/TP1/Pmid/TP2 calculation (spec §5)
- [ ] Multi-timeframe confirmation logic (spec §6)
- [ ] Full pipeline test: raw candles in → six trade levels out, matching
      the worked EURUSD example end-to-end

## M4 — Risk Management (Weeks 5–6)

- [ ] Fixed-risk position sizing (φ=2%, spec §7)
- [ ] Volatility-based stop loss (document your volatility estimator —
      the spec references GARCH(1,1) conceptually; a simpler ATR-based
      proxy is an acceptable engineering substitute *if documented as such*)
- [ ] RR filter (per-asset-class minimums)
- [ ] Midpoint trailing reduction (spec §8)

## M5 — Execution Layer (Weeks 6–8)

- [ ] Broker/exchange adapter interface (start with a paper-trading/mock
      adapter; real broker integration is a stretch goal)
- [ ] Order placement, SL/TP attachment, partial close at TP1
- [ ] "Burned N3" memory (prevents re-entry on a level that already hit SL)

## M6 — Backtesting Engine (parallel with M4/M5)

- [ ] Historical replay engine consuming the same M1–M3 pipeline
- [ ] Performance report (win rate, RR distribution, drawdown)
- [ ] This is the fastest way to validate M1–M3 correctness without a live
      broker — prioritize contributors here early

## M7 — Dashboard (Weeks 7–9, parallel)

- [ ] Live chart with detected nodes overlaid
- [ ] Trade level visualization
- [ ] Stats panel (signals, fired, win rate, NSI distribution)

## Interface Contracts (unblock parallel work)

Define these early (M0) so M1–M7 teams can work simultaneously against
stable interfaces instead of waiting on each other:

```
Candle            -> { time, open, high, low, close, volume }
Node              -> { time, price, type: PEAK|TROUGH, label: Z|N1|S1|N2|S2|N3 }
CycleCandidate    -> { nodes: Node[6], nsi: float, quality: QualityResult }
QualityResult     -> { ok: bool, score: float, reason: str }
TradeLevels       -> { entry, sl, tp1, tp2, pmid, side: BUY|SELL }
```

## Definition of Done (every milestone)

- All formulas implemented match the worked numeric examples in the spec
  (exact reproduction, not "close enough")
- Every engineering-choice constant is in a config file with a comment,
  not hardcoded inline
- Test coverage on the module's public interface
- Owner has reviewed and approved the PR
