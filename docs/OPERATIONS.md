# Operations Guide

## Runtime diagnostics

Run the default checks:

```powershell
python -m nds_bot doctor
```

Validate a real candle file and output directory:

```powershell
python -m nds_bot doctor `
  --config config\default.yaml `
  --csv data\samples\documented_bull_cycle_execution.csv `
  --output-dir results `
  --strict
```

JSON output:

```powershell
python -m nds_bot doctor --format json
```

## Runtime logging

Global logging options must appear before the subcommand:

```powershell
python -m nds_bot `
  --log-level INFO `
  --log-format json `
  --log-file results\runtime.jsonl `
  paper `
  --csv data\samples\documented_bull_cycle_execution.csv `
  --config config\default.yaml `
  --extrema-window 1 `
  --symbol EURUSD `
  --orders-output results\paper_orders.csv `
  --trades-output results\paper_trades.csv `
  --equity-output results\paper_equity.csv
```

Default log level is `WARNING`, so existing CLI output remains quiet unless a higher verbosity is requested.

## CI

The CI workflow checks:

- Python 3.11 and 3.12
- Ruff lint
- Ruff formatting
- Pytest
- branch-aware coverage with a 70% initial threshold

## Release build

Create a local release candidate:

```powershell
python -m pip install build
python -m ruff check .
python -m ruff format --check .
python -m pytest -v
python -m nds_bot doctor --strict
python -m build
```

The tag workflow builds artifacts for tags matching `v*`. It does not publish to PyPI automatically.
