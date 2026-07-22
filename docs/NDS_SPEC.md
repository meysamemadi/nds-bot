# NDS Model — Technical Specification

This is the ground-truth specification contributors implement against.
It describes formulas and required behavior, not implementation. Two
formulas producing the same numbers on the same inputs are both "correct"
regardless of internal design.

## §0 — Provenance Principle (read this first)

Every formula below is tagged:

- **[DOCUMENTED]** — comes directly from a named NDS research paper, with
  exact formula and (where available) the paper's own stated values. These
  are **not up for debate** in a PR — implement them exactly.
- **[ENGINEERING CHOICE]** — a filter/threshold that is reasonable and in
  the spirit of the model, but has no citation in the source papers. Your
  team may implement these, tune them, or replace them entirely — just
  document your choice and reasoning in the code and in your PR.

Do not present an engineering choice as if it were documented, and don't
silently skip a documented formula because you think you have a better
idea — open an issue and discuss first.

---

## §1 — Scale Requirement [DOCUMENTED]

All price displacement, ratio, and symmetry calculations MUST operate on
log-transformed prices, never raw price differences.

```
Δ(P1, P2) = ln(P2 / P1)
```

**Why:** a 50% rally and a 33.3% pullback are numerically different in
linear terms but represent an identical round-trip in log terms
(ln(1.5) = +0.4055, ln(1/1.5) = −0.4055). Every formula in this spec
assumes its inputs are already log-transformed.

**Test:** given P1=100, P2=150, P3=100, confirm your Δ function returns
+0.4055 and −0.4055 (not +50 and −33.3, and not +50 and −50).

---

## §2 — Node/Topology Detection [DOCUMENTED definition, ENGINEERING CHOICE parameters]

**[DOCUMENTED]** A node is a local extremum: price P(t) is a peak if
P(t) ≥ P(t±ε) for a symmetric neighborhood ε, or a trough under the
reversed inequality.

**[ENGINEERING CHOICE]** The neighborhood size (how many candles left/right
to check — "the 6-and-6 test") and the minimum swing threshold (% move
required to count as a real swing vs. noise) are not specified numerically
in the source papers. Pick sensible defaults (start around 5–8 candles,
0.05–0.2% threshold depending on asset class) and make them configurable.

**[DOCUMENTED]** A full cycle is exactly six nodes in strict alternating
order: Z (origin) → N1 → S1 → N2 → S2 → N3, where for a bull cycle
(Z=trough, N3=peak):

```
N1 > Z
Z < S1 < N1
N2 > N1
S1 < S2 < N2
N3 > N2
```

(Bear cycle: same structure, all inequalities reversed — Z=peak, N3=trough.)

**There is no seventh node.** A cycle closes at N3. If a new higher
peak appears after N3, that starts a new cycle from a new Z — it does not
extend the old sequence.

### Worked example (implement this exactly, verify your output matches)

| Node | Price (EURUSD) |
|---|---|
| Z | 1.08000 |
| N1 | 1.08650 |
| S1 | 1.08230 |
| N2 | 1.09100 |
| S2 | 1.08600 |
| N3 | 1.09480 |

All five structural inequalities above must hold for this example — use
it as your first unit test fixture.

---

## §3 — Hook Retracement Ratio [DOCUMENTED]

Each correction (pullback) retraces a fraction α of its preceding rally:

```
K = α · R
α = 0.86   (empirically observed constant, cited across multiple source papers)
```

For the worked example above:
```
Δ1 (rally Z→N1)  = ln(1.08650/1.08000) = +0.00602
Δ2 (hook N1→S1)  = ln(1.08230/1.08650) = −0.00387
hook_ratio = |Δ2| / |Δ1| = 0.643
```

**[ENGINEERING CHOICE]** How much tolerance to allow around 0.86 (i.e., a
valid range like 0.25–0.92) is not specified in source papers — only the
ideal value 0.86 is documented. Decide and document your own tolerance
band.

---

## §4 — Nodal Symmetry Index (NSI) [DOCUMENTED]

```
NSI = (1/n) · Σ |Δᵢ − Δᵢ₋ₖ|  /  mean(|Δ|)
k = 2   (periodicity — compares each leg to the same-type leg two positions back)
```

For the 5-leg cycle (Δ1..Δ5), with k=2, the three comparisons are
(Δ1,Δ3), (Δ2,Δ4), (Δ3,Δ5).

### Worked example — healthy cycle (use as test fixture)

| Leg | \|Δ\| (%) |
|---|---|
| Δ1 | 0.602 |
| Δ2 | 0.387 |
| Δ3 | 0.804 |
| Δ4 | 0.458 |
| Δ5 | 0.810 |

Expected: NSI ≈ **0.152**

### Worked example — unhealthy cycle (should be rejected)

| Leg | \|Δ\| (%) |
|---|---|
| Δ1 | 0.40 |
| Δ2 | 0.10 |
| Δ3 | 1.90 |
| Δ4 | 1.50 |
| Δ5 | 0.35 |

Expected: NSI ≈ **1.745**

**[ENGINEERING CHOICE]** The maximum acceptable NSI (a common choice is
around 0.5–0.6) is not itself specified in source papers — only the
formula is documented. Pick and justify your threshold.

---

## §5 — Reversal Criteria [DOCUMENTED]

Two independent signals, either or both usable as confirmation:

**5a. Slope sign change** — a genuine reversal node exhibits a sign change
in the local price derivative immediately before vs. after:

```
Sign(dP(tₘ)/dt) ≠ Sign(dP(tₘ₊₁)/dt)
```

In discrete terms: compare the sign of (close[t] - close[t-1]) across the
candidate node.

**5b. Diminishing displacement with growing composite** — an early warning
that a reversal is approaching:

```
|ΔPₘ,ₘ₊₁| < |ΔPₘ₋₁,ₘ|     AND     |C_(n,n+k)| > |C_(n,n+k-1)|
```

i.e., each new swing is smaller than the last, while the cumulative/
composite move is still making new extremes. This is a deceleration
signal, not a hard trigger — treat it as a warning flag, not an entry
condition by itself.

---

## §6 — Multi-Timeframe Confirmation [DOCUMENTED principle, ENGINEERING CHOICE mechanics]

**[DOCUMENTED]** Higher timeframes structurally embed lower-timeframe
cycles (a cycle on H1 is composed of smaller complete cycles on M15, which
are themselves composed of complete cycles on M1). A signal on a lower
timeframe should not contradict the structure visible on a higher
timeframe.

**[ENGINEERING CHOICE]** The exact confirmation rule (e.g. "require at
least a 3-of-6 partial cycle in the same direction on the higher
timeframe") is an implementation decision. Design and document your own
rule; a reasonable starting point is requiring the higher timeframe to not
show a *completed, opposite-direction* 6-node cycle.

---

## §7 — Trade Levels [DOCUMENTED]

Given a valid 6-node cycle with wave = |N3 − Z|:

```
entry = N3
TP1   = S2
TP2   = N3 ∓ α · wave        (minus for SELL, plus for BUY; α = 0.86)
Pmid  = (Z + TP2) / 2
```

### Worked example (continuing the EURUSD fixture, SELL side)

```
wave = |1.09480 − 1.08000| = 0.01480
entry = 1.09480
TP1   = 1.08600  (= S2)
TP2   = 1.09480 − 0.86×0.01480 = 1.08207
Pmid  = (1.08000 + 1.08207) / 2 = 1.08103
```

**[ENGINEERING CHOICE]** Stop-loss placement is not itself given a single
documented formula — the model references volatility-adjusted stops
conceptually (a GARCH-style estimator is one legitimate approach; a
simpler ATR-based proxy is an acceptable and clearly-labeled engineering
substitute). Whatever volatility estimator you pick, document it and its
parameters.

---

## §8 — Risk Management [DOCUMENTED core, ENGINEERING CHOICE mechanics]

**[DOCUMENTED]** Fixed fractional risk per trade:

```
R = Balance × φ
φ = 0.02   (2% risk per trade)
```

Position size follows from R and your stop-loss distance:

```
lot_size = R / (|entry − SL| × contract_size)
```

**[DOCUMENTED]** Midpoint trailing — once price crosses Pmid toward TP2,
position is progressively reduced:

```
λ = (k · σₜ) / |TP2 − Pmid|
N_trail(t) = N_final × [1 − λ · |P(t) − Pmid| / |TP2 − Pmid|]
```

where σₜ is your chosen volatility estimate (see §7) and k is a tunable
sensitivity constant — **[ENGINEERING CHOICE]** for k's value; k=1.0 is a
reasonable starting point but not itself specified numerically in source
papers.

**[ENGINEERING CHOICE]** Minimum acceptable risk/reward ratio before
taking a trade is not specified numerically in source papers. Pick and
document a threshold (many implementations use something in the 1.5–2.0
range) — but treat it explicitly as your team's decision, not spec.

---

## Changelog

- v1.0 — initial spec extracted from NDS research paper review.
