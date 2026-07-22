# Quant Geometrical Trader — NDS Bot (Student Build)

> **Project Owner:** see [`SETUP.md`](SETUP.md) for one-time repo setup
> (branch protection, project board, inviting contributors).

A trading bot implementing **Nodal Displacement Sequencing (NDS)** — a market
geometry model based on fractal cycle analysis, node detection, and symmetry
measurement — built collaboratively by contributors under supervision.

## What This Project Is

This repo is a **learning + build project**. Contributors implement an
algorithmic trading system from a written specification (see
[`docs/NDS_SPEC.md`](docs/NDS_SPEC.md)), not from a reference implementation.
There is no "correct" existing codebase to copy from — the spec describes
*what* the system must do mathematically; *how* you implement it is up to
you and your team, subject to review.

## Roles

| Role | Responsibility |
|---|---|
| **Project Owner (Maintainer)** | Sets roadmap, owns `main`, reviews & merges PRs, is the final authority on whether an implementation matches the spec |
| **Contributors** | Pick up issues, work on feature branches, open PRs, respond to review feedback |

The Project Owner does **not** write feature code directly. All feature work
flows through PRs reviewed by the Owner (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Project Structure (target)

```
nds-bot/
├── docs/
│   ├── NDS_SPEC.md          # the formal spec — READ THIS FIRST
│   ├── ROADMAP.md           # milestones & module breakdown
│   └── GLOSSARY.md          # symbols, terms, notation reference
├── src/
│   ├── data/                # market data ingestion (candles, multi-timeframe)
│   ├── topology/             # node/swing detection (Z, N1, S1, N2, S2, N3)
│   ├── quality/              # NSI, hook ratio, symmetry filters
│   ├── levels/                # entry/SL/TP/Pmid calculation
│   ├── risk/                  # position sizing, risk management
│   ├── execution/           # broker/exchange integration
│   ├── backtest/            # historical simulation engine
│   └── dashboard/            # monitoring UI
├── tests/                    # unit + integration tests, one dir per module above
└── .github/                  # PR/issue templates, CI config
```

## Getting Started (Contributors)

This repo is public — no invite or access request needed. Just fork it.

1. Read `docs/NDS_SPEC.md` in full before writing any code.
2. Read `CONTRIBUTING.md` for the fork workflow, branching, commit, and PR conventions.
3. Check the [Project Board](../../projects) for open issues tagged `good-first-issue`.
4. Comment on an issue to claim it before starting work.
5. Fork → branch → implement → write tests → open a PR against `develop` (not `main`).

## Non-Negotiable Rules

- **No formula in `docs/NDS_SPEC.md` may be altered without Owner sign-off.**
  If you think a formula is wrong or a threshold should change, open an issue
  and discuss — don't just change it in your PR.
- **Every module needs tests.** PRs without tests will not be reviewed.
- **Every non-obvious threshold/constant must be flagged** as either
  "per spec §X" (cite the section) or "engineering choice — needs review."
  This mirrors how the spec itself distinguishes documented formulas from
  undocumented heuristics — see `docs/NDS_SPEC.md` §0.
