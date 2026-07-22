# Glossary

## Nodes & Sequence

| Symbol | Meaning |
|---|---|
| Z | Origin node of a cycle (trough in a bull cycle, peak in a bear cycle) |
| N1, N2, N3 | Successive peaks (bull cycle) / troughs (bear cycle) |
| S1, S2 | Successive troughs (bull cycle) / peaks (bear cycle), between the N nodes |
| R (Rally) | An advancing leg, e.g. Z→N1 |
| K (Correction/Hook) | A retracing leg, e.g. N1→S1 |
| C (Cycle) | Net movement of a full rally-correction pair: C = R − K |

## Greek Letters

| Symbol | Read as | Meaning |
|---|---|---|
| α (alpha) | alpha | Hook retracement ratio, 0.86 |
| δ (lowercase delta) | delta | Position-size reduction coefficient |
| Δ (uppercase delta) | delta | Displacement/difference between two nodes |
| φ (phi) | phi | Fixed risk fraction per trade, 0.02 |
| σ (sigma) | sigma | Volatility estimate |
| λ (lambda) | lambda | Midpoint-trailing sensitivity coefficient |
| ω, α, β (GARCH context) | omega, alpha, beta | GARCH(1,1) volatility model parameters — not the same α as the hook ratio; context disambiguates |

## Metrics

| Term | Meaning |
|---|---|
| NSI | Nodal Symmetry Index — measures how symmetric same-type legs are within a cycle |
| Hook ratio | \|correction\| / \|preceding rally\|, ideally ≈ 0.86 |
| G% | Percentage position of entry price along the Z→TP2 path — used for position sizing, NOT entry timing |
| RR | Risk/reward ratio = \|TP2 − entry\| / \|entry − SL\| |

## Trade Levels

| Term | Meaning |
|---|---|
| Entry / exec_p | Execution price, = N3 |
| SL | Stop loss |
| TP1 | First take-profit target, = S2 |
| TP2 | Final take-profit target |
| Pmid | Midpoint between Z and TP2, used as a trailing-reduction trigger |

## Process Terms (this repo)

| Term | Meaning |
|---|---|
| Spec | `docs/NDS_SPEC.md` — the formal requirements document |
| DOCUMENTED | A formula with a citation in NDS source papers — not open to reinterpretation |
| ENGINEERING CHOICE | A parameter/filter without a paper citation — team's decision, must be documented as such |
| Owner | The project maintainer who reviews and merges all PRs |
