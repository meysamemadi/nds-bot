# Changelog

All notable changes to this project are documented here.

## [1.0.0] - Unreleased

### Added

- Deterministic NDS topology, quality validation, replay, and signal generation.
- Next-candle execution, gap-aware exits, trading costs, broker lot sizing, and margin checks.
- Account simulation, equity and drawdown reporting, chronological validation, walk-forward testing, and portfolio backtesting.
- Offline paper trading through a broker-adapter protocol.
- Structured text/JSON logging and lifecycle logs for paper sessions.
- `doctor` runtime diagnostics command.
- GitHub Actions CI for Ruff, tests, branch coverage, and package build verification.

### Safety and scope

- Paper trading is offline and does not place real orders.
- Live broker credentials and live-order submission are not part of v1.0.
- Random Forest remains an optional future research layer and is not required by the deterministic NDS engine.
