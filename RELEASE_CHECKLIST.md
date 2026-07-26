# NDS Bot v1.0 Release Checklist

## Source and quality

- [ ] Working tree is clean.
- [ ] `python -m ruff check .` passes.
- [ ] `python -m ruff format --check .` passes.
- [ ] `python -m pytest -v` passes.
- [ ] Coverage is at least 70% branch-aware coverage.
- [ ] `python -m nds_bot doctor --strict` passes.

## Functional smoke tests

- [ ] `scan`, `replay`, and `signals` run on the documented sample.
- [ ] `backtest` produces trade and equity CSV outputs.
- [ ] `validate` runs in HOLDOUT and WALK_FORWARD modes.
- [ ] `portfolio` produces summary and combined equity outputs.
- [ ] `paper` produces order, trade, and equity outputs without network access.
- [ ] Text and JSON logging are readable.

## Documentation and packaging

- [ ] `CHANGELOG.md` release date is updated.
- [ ] Project version in `pyproject.toml` is set to `1.0.0`.
- [ ] README installation and examples are current.
- [ ] `python -m build` creates a wheel and source distribution.
- [ ] Wheel installs successfully in a clean virtual environment.

## Git and release

- [ ] Final changes are committed and pushed.
- [ ] Pull request is reviewed and merged into the release branch.
- [ ] Tag `v1.0.0` is created and pushed.
- [ ] GitHub release artifacts are verified.
