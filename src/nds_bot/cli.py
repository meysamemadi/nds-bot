import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from nds_bot.backtest.account import (
    AccountPolicy,
    OverlapPolicy,
)
from nds_bot.backtest.contracts import (
    BelowMinimumLotPolicy,
    ContractSpecification,
)
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import (
    ExecutionPolicy,
    GapFillMode,
    IntrabarPriority,
)
from nds_bot.backtest.margin import (
    InsufficientMarginPolicy,
    MarginPolicy,
)
from nds_bot.backtest.portfolio import (
    PortfolioResult,
    run_portfolio_backtest,
)
from nds_bot.backtest.runner import (
    BacktestResult,
    run_backtest,
)
from nds_bot.backtest.validation import (
    BoundaryTradePolicy,
    HoldoutValidationConfig,
    HoldoutValidationResult,
    ValidationSegment,
    run_holdout_validation,
)
from nds_bot.backtest.walk_forward import (
    WalkForwardValidationConfig,
    WalkForwardValidationResult,
    run_walk_forward_validation,
)
from nds_bot.data.csv_loader import (
    CandleCsvError,
    load_candles_csv,
)
from nds_bot.data.equity_csv import (
    EquityCsvError,
    write_equity_csv,
)
from nds_bot.data.portfolio_csv import (
    PortfolioCsvError,
    write_portfolio_equity_csv,
    write_portfolio_summary_csv,
)
from nds_bot.data.portfolio_manifest import (
    PortfolioManifestError,
    load_portfolio_datasets,
)
from nds_bot.data.signal_csv import (
    SignalCsvError,
    write_signals_csv,
)
from nds_bot.data.trade_csv import (
    TradeCsvError,
    write_sized_trades_csv,
)
from nds_bot.data.validation_csv import (
    ValidationCsvError,
    write_validation_csv,
)
from nds_bot.data.walk_forward_csv import (
    WalkForwardCsvError,
    write_walk_forward_csv,
)
from nds_bot.models import Candle, Node
from nds_bot.pipeline import (
    CycleAnalysis,
    ScanConfig,
    ScanResult,
    scan_candles,
)
from nds_bot.replay import (
    ReplayResult,
    replay_candles,
)
from nds_bot.reporting import (
    build_replay_report,
    build_scan_report,
    render_json,
)
from nds_bot.settings import (
    ConfigurationError,
    load_scan_config,
)
from nds_bot.signals import build_trade_signals

EXIT_SUCCESS = 0
EXIT_ERROR = 1

OUTPUT_FORMATS = (
    "text",
    "json",
)

VALIDATION_MODES = (
    "HOLDOUT",
    "WALK_FORWARD",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the NDS command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="nds-bot",
        description=("Detect, evaluate, replay, and backtest NDS cycles in candle CSV data."),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a complete candle CSV file.",
    )

    _add_input_arguments(scan_parser)
    _add_output_format_argument(scan_parser)

    replay_parser = subparsers.add_parser(
        "replay",
        help=("Replay candles chronologically without look-ahead bias."),
    )

    _add_input_arguments(replay_parser)
    _add_output_format_argument(replay_parser)

    signals_parser = subparsers.add_parser(
        "signals",
        help=("Generate BUY and SELL signals from valid replay events."),
    )

    _add_input_arguments(signals_parser)

    signals_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path of the output signal CSV file.",
    )

    backtest_parser = subparsers.add_parser(
        "backtest",
        help=(
            "Run chronological replay, execute signals, simulate an account, and export results."
        ),
    )

    _add_input_arguments(backtest_parser)

    backtest_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=("Path of the account-sized and cost-adjusted trade CSV file."),
    )

    backtest_parser.add_argument(
        "--reward-to-risk",
        type=float,
        default=2.0,
        help=("Take-profit reward-to-risk ratio (default: 2.0)."),
    )

    backtest_parser.add_argument(
        "--stop-buffer-fraction",
        type=float,
        default=0.0,
        help=("Fractional Stop Loss buffer beyond N3 (default: 0)."),
    )

    backtest_parser.add_argument(
        "--intrabar-priority",
        choices=tuple(priority.value for priority in IntrabarPriority),
        default=IntrabarPriority.STOP_FIRST.value,
        help=("Resolution when Stop Loss and Take Profit are touched inside the same candle."),
    )

    backtest_parser.add_argument(
        "--gap-fill-mode",
        choices=tuple(mode.value for mode in GapFillMode),
        default=GapFillMode.OPEN_PRICE.value,
        help=(
            "Fill price used when a candle opens beyond "
            "Stop Loss or Take Profit: OPEN_PRICE or "
            "LEVEL_PRICE (default: OPEN_PRICE)."
        ),
    )

    backtest_parser.add_argument(
        "--initial-balance",
        type=float,
        default=10_000.0,
        help=("Starting account balance (default: 10000)."),
    )

    backtest_parser.add_argument(
        "--risk-fraction",
        type=float,
        default=0.01,
        help=("Fraction of current balance risked per trade (default: 0.01)."),
    )

    backtest_parser.add_argument(
        "--overlap-policy",
        choices=tuple(policy.value for policy in OverlapPolicy),
        default=OverlapPolicy.SKIP.value,
        help=("Resolution for overlapping trades: SKIP or RAISE."),
    )

    backtest_parser.add_argument(
        "--equity-output",
        type=Path,
        default=None,
        help=("Path of the equity-curve CSV file. Defaults to equity.csv beside the trade output."),
    )

    backtest_parser.add_argument(
        "--spread-fraction",
        type=float,
        default=0.0,
        help=("Full bid-ask spread as a fraction of price (default: 0)."),
    )

    backtest_parser.add_argument(
        "--slippage-fraction",
        type=float,
        default=0.0,
        help=("Adverse slippage applied to each fill (default: 0)."),
    )

    backtest_parser.add_argument(
        "--commission-fraction",
        type=float,
        default=0.0,
        help=("Commission fraction charged on notional for each side (default: 0)."),
    )

    backtest_parser.add_argument(
        "--contract-size",
        type=float,
        default=None,
        help=(
            "Enable broker lot sizing with the number of underlying units represented by one lot."
        ),
    )

    backtest_parser.add_argument(
        "--minimum-lot",
        type=float,
        default=None,
        help=("Smallest broker-accepted lot volume (default when enabled: 0.01)."),
    )

    backtest_parser.add_argument(
        "--maximum-lot",
        type=float,
        default=None,
        help=("Largest broker-accepted lot volume (default when enabled: 100)."),
    )

    backtest_parser.add_argument(
        "--lot-step",
        type=float,
        default=None,
        help=("Allowed broker lot increment (default when enabled: 0.01)."),
    )

    backtest_parser.add_argument(
        "--below-minimum-lot-policy",
        choices=tuple(policy.value for policy in BelowMinimumLotPolicy),
        default=None,
        help=("Resolution when the risk budget cannot fund one minimum lot: SKIP or RAISE."),
    )

    backtest_parser.add_argument(
        "--leverage",
        type=float,
        default=None,
        help=(
            "Enable entry-time margin checks with the specified account leverage, for example 100."
        ),
    )

    backtest_parser.add_argument(
        "--insufficient-margin-policy",
        choices=tuple(policy.value for policy in InsufficientMarginPolicy),
        default=None,
        help=("Resolution when required margin exceeds account equity: SKIP or RAISE."),
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help=("Run chronological holdout or walk-forward out-of-sample validation."),
    )

    _add_input_arguments(validate_parser)

    validate_parser.add_argument(
        "--mode",
        choices=VALIDATION_MODES,
        default="HOLDOUT",
        help=("Validation mode: HOLDOUT or WALK_FORWARD (default: HOLDOUT)."),
    )

    validate_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path of the validation summary CSV file.",
    )

    validate_parser.add_argument(
        "--train-fraction",
        type=float,
        default=0.70,
        help=("Chronological train fraction used by HOLDOUT mode (default: 0.70)."),
    )

    validate_parser.add_argument(
        "--boundary-trade-policy",
        choices=tuple(policy.value for policy in BoundaryTradePolicy),
        default=BoundaryTradePolicy.EXCLUDE.value,
        help=("Resolution for a trade crossing a validation boundary: EXCLUDE or ASSIGN_TO_TRAIN."),
    )

    validate_parser.add_argument(
        "--initial-train-candles",
        type=int,
        default=None,
        help=("Initial expanding train-window size required by WALK_FORWARD mode."),
    )

    validate_parser.add_argument(
        "--test-candles",
        type=int,
        default=None,
        help=("Test-window size required by WALK_FORWARD mode."),
    )

    validate_parser.add_argument(
        "--step-candles",
        type=int,
        default=None,
        help=("Distance between walk-forward split points. Defaults to the test-window size."),
    )

    _add_validation_policy_arguments(validate_parser)

    portfolio_parser = subparsers.add_parser(
        "portfolio",
        help=("Run independently allocated multi-symbol and multi-timeframe portfolio backtests."),
    )

    portfolio_parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path of the portfolio dataset manifest CSV.",
    )

    portfolio_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path of the portfolio summary CSV file.",
    )

    portfolio_parser.add_argument(
        "--equity-output",
        type=Path,
        default=None,
        help=(
            "Path of the combined portfolio equity CSV. "
            "Defaults to portfolio_equity.csv beside the summary."
        ),
    )

    _add_validation_policy_arguments(portfolio_parser)

    return parser


def _add_input_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add common candle and configuration arguments."""
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to the candle CSV file.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default.yaml"),
        help=("Path to the YAML configuration file (default: config/default.yaml)."),
    )

    parser.add_argument(
        "--extrema-window",
        type=int,
        default=None,
        help=("Override the extrema window defined in the YAML configuration."),
    )


def _add_output_format_argument(
    parser: argparse.ArgumentParser,
) -> None:
    """Add the text or JSON output-format argument."""
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=OUTPUT_FORMATS,
        default="text",
        help="Output format: text or json.",
    )


def _add_validation_policy_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add execution, account, cost, contract, and margin options."""
    parser.add_argument(
        "--reward-to-risk",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--stop-buffer-fraction",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--intrabar-priority",
        choices=tuple(priority.value for priority in IntrabarPriority),
        default=IntrabarPriority.STOP_FIRST.value,
    )
    parser.add_argument(
        "--gap-fill-mode",
        choices=tuple(mode.value for mode in GapFillMode),
        default=GapFillMode.OPEN_PRICE.value,
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=10_000.0,
    )
    parser.add_argument(
        "--risk-fraction",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--overlap-policy",
        choices=tuple(policy.value for policy in OverlapPolicy),
        default=OverlapPolicy.SKIP.value,
    )
    parser.add_argument(
        "--spread-fraction",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--slippage-fraction",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--commission-fraction",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--contract-size",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--minimum-lot",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--maximum-lot",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--lot-step",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--below-minimum-lot-policy",
        choices=tuple(policy.value for policy in BelowMinimumLotPolicy),
        default=None,
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--insufficient-margin-policy",
        choices=tuple(policy.value for policy in InsufficientMarginPolicy),
        default=None,
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the NDS command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "scan":
        return _run_scan(arguments)

    if arguments.command == "replay":
        return _run_replay(arguments)

    if arguments.command == "signals":
        return _run_signals(arguments)

    if arguments.command == "backtest":
        return _run_backtest(arguments)

    if arguments.command == "validate":
        return _run_validate(arguments)

    if arguments.command == "portfolio":
        return _run_portfolio(arguments)

    parser.error(f"Unsupported command: {arguments.command}")

    return EXIT_ERROR


def _run_scan(
    arguments: argparse.Namespace,
) -> int:
    """Execute a complete batch scan."""
    try:
        config, candles = _load_inputs(arguments)

        result = scan_candles(
            candles,
            config=config,
        )

    except (
        ConfigurationError,
        CandleCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    if arguments.output_format == "json":
        report = build_scan_report(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
        )

        print(render_json(report))

    else:
        _print_scan_result(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
        )

    return EXIT_SUCCESS


def _run_replay(
    arguments: argparse.Namespace,
) -> int:
    """Execute a chronological candle replay."""
    try:
        config, candles = _load_inputs(arguments)

        result = replay_candles(
            candles,
            config=config,
        )

    except (
        ConfigurationError,
        CandleCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    if arguments.output_format == "json":
        report = build_replay_report(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
        )

        print(render_json(report))

    else:
        _print_replay_result(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
        )

    return EXIT_SUCCESS


def _run_signals(
    arguments: argparse.Namespace,
) -> int:
    """Generate and export signals from replay events."""
    try:
        config, candles = _load_inputs(arguments)

        replay_result = replay_candles(
            candles,
            config=config,
        )

        signals = build_trade_signals(
            candles,
            replay_result,
        )

        output_path = write_signals_csv(
            signals,
            arguments.output,
        )

    except (
        ConfigurationError,
        CandleCsvError,
        SignalCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    print("NDS signal export completed")

    _print_input_summary(
        candle_count=len(candles),
        csv_path=arguments.csv,
        config_path=arguments.config,
        extrema_window=config.extrema_window,
    )

    print(f"Replay events: {len(replay_result.events)}")

    print(f"Valid events: {len(replay_result.valid_events)}")

    print(f"Signals: {len(signals)}")
    print(f"Output file: {output_path}")

    return EXIT_SUCCESS


def _run_backtest(
    arguments: argparse.Namespace,
) -> int:
    """Run and export a complete NDS backtest."""
    try:
        config, candles = _load_inputs(arguments)

        execution_policy = ExecutionPolicy(
            reward_to_risk=arguments.reward_to_risk,
            stop_buffer_fraction=(arguments.stop_buffer_fraction),
            intrabar_priority=IntrabarPriority(arguments.intrabar_priority),
            gap_fill_mode=GapFillMode(arguments.gap_fill_mode),
        )

        account_policy = AccountPolicy(
            initial_balance=arguments.initial_balance,
            risk_fraction=arguments.risk_fraction,
            overlap_policy=OverlapPolicy(arguments.overlap_policy),
        )

        cost_policy = TradingCostPolicy(
            spread_fraction=arguments.spread_fraction,
            slippage_fraction=arguments.slippage_fraction,
            commission_fraction=(arguments.commission_fraction),
        )

        contract_specification = _build_contract_specification(arguments)

        margin_policy = _build_margin_policy(arguments)

        result = run_backtest(
            candles,
            config=config,
            execution_policy=execution_policy,
            account_policy=account_policy,
            cost_policy=cost_policy,
            contract_specification=(contract_specification),
            margin_policy=margin_policy,
        )

        account_result = result.account

        if account_result is None:
            raise ValueError("Account simulation result is missing.")

        trade_output_path = write_sized_trades_csv(
            account_result.trades,
            arguments.output,
        )

        equity_output_path = write_equity_csv(
            account_result.equity_curve,
            _resolve_equity_output_path(
                trade_output_path=trade_output_path,
                equity_output_path=(arguments.equity_output),
            ),
        )

    except (
        ConfigurationError,
        CandleCsvError,
        TradeCsvError,
        EquityCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    _print_backtest_result(
        result,
        candle_count=len(candles),
        csv_path=arguments.csv,
        config_path=arguments.config,
        trade_output_path=trade_output_path,
        equity_output_path=equity_output_path,
        extrema_window=config.extrema_window,
        execution_policy=execution_policy,
        account_policy=account_policy,
        cost_policy=cost_policy,
        contract_specification=(contract_specification),
        margin_policy=margin_policy,
    )

    return EXIT_SUCCESS


def _run_validate(
    arguments: argparse.Namespace,
) -> int:
    """Run chronological holdout or walk-forward validation."""
    try:
        config, candles = _load_inputs(arguments)

        execution_policy = ExecutionPolicy(
            reward_to_risk=arguments.reward_to_risk,
            stop_buffer_fraction=(arguments.stop_buffer_fraction),
            intrabar_priority=IntrabarPriority(arguments.intrabar_priority),
            gap_fill_mode=GapFillMode(arguments.gap_fill_mode),
        )

        account_policy = AccountPolicy(
            initial_balance=arguments.initial_balance,
            risk_fraction=arguments.risk_fraction,
            overlap_policy=OverlapPolicy(arguments.overlap_policy),
        )

        cost_policy = TradingCostPolicy(
            spread_fraction=arguments.spread_fraction,
            slippage_fraction=arguments.slippage_fraction,
            commission_fraction=(arguments.commission_fraction),
        )

        contract_specification = _build_contract_specification(arguments)
        margin_policy = _build_margin_policy(arguments)
        boundary_policy = BoundaryTradePolicy(arguments.boundary_trade_policy)

        if arguments.mode == "HOLDOUT":
            result = run_holdout_validation(
                candles,
                validation_config=HoldoutValidationConfig(
                    train_fraction=arguments.train_fraction,
                    boundary_trade_policy=boundary_policy,
                ),
                config=config,
                execution_policy=execution_policy,
                account_policy=account_policy,
                cost_policy=cost_policy,
                contract_specification=(contract_specification),
                margin_policy=margin_policy,
            )

            output_path = write_validation_csv(
                result,
                arguments.output,
            )

        else:
            if arguments.initial_train_candles is None:
                raise ValueError("Initial train candles are required for WALK_FORWARD mode.")

            if arguments.test_candles is None:
                raise ValueError("Test candles are required for WALK_FORWARD mode.")

            result = run_walk_forward_validation(
                candles,
                validation_config=(
                    WalkForwardValidationConfig(
                        initial_train_candles=(arguments.initial_train_candles),
                        test_candles=arguments.test_candles,
                        step_candles=arguments.step_candles,
                        boundary_trade_policy=boundary_policy,
                    )
                ),
                config=config,
                execution_policy=execution_policy,
                account_policy=account_policy,
                cost_policy=cost_policy,
                contract_specification=(contract_specification),
                margin_policy=margin_policy,
            )

            output_path = write_walk_forward_csv(
                result,
                arguments.output,
            )

    except (
        ConfigurationError,
        CandleCsvError,
        ValidationCsvError,
        WalkForwardCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    if arguments.mode == "HOLDOUT":
        _print_holdout_validation_result(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
            output_path=output_path,
        )
    else:
        _print_walk_forward_validation_result(
            result,
            candle_count=len(candles),
            csv_path=arguments.csv,
            config_path=arguments.config,
            extrema_window=config.extrema_window,
            output_path=output_path,
        )

    return EXIT_SUCCESS


def _run_portfolio(
    arguments: argparse.Namespace,
) -> int:
    """Run a multi-symbol and multi-timeframe portfolio backtest."""
    try:
        datasets = load_portfolio_datasets(arguments.manifest)

        execution_policy = ExecutionPolicy(
            reward_to_risk=arguments.reward_to_risk,
            stop_buffer_fraction=(arguments.stop_buffer_fraction),
            intrabar_priority=IntrabarPriority(arguments.intrabar_priority),
            gap_fill_mode=GapFillMode(arguments.gap_fill_mode),
        )

        account_policy = AccountPolicy(
            initial_balance=arguments.initial_balance,
            risk_fraction=arguments.risk_fraction,
            overlap_policy=OverlapPolicy(arguments.overlap_policy),
        )

        cost_policy = TradingCostPolicy(
            spread_fraction=arguments.spread_fraction,
            slippage_fraction=arguments.slippage_fraction,
            commission_fraction=(arguments.commission_fraction),
        )

        contract_specification = _build_contract_specification(arguments)
        margin_policy = _build_margin_policy(arguments)

        result = run_portfolio_backtest(
            datasets,
            account_policy=account_policy,
            execution_policy=execution_policy,
            cost_policy=cost_policy,
            contract_specification=contract_specification,
            margin_policy=margin_policy,
        )

        summary_output_path = write_portfolio_summary_csv(
            result,
            arguments.output,
        )
        equity_output_path = write_portfolio_equity_csv(
            result,
            _resolve_portfolio_equity_output_path(
                summary_output_path=summary_output_path,
                equity_output_path=arguments.equity_output,
            ),
        )

    except (
        PortfolioManifestError,
        ConfigurationError,
        CandleCsvError,
        PortfolioCsvError,
        ValueError,
    ) as error:
        return _report_error(error)

    _print_portfolio_result(
        result,
        manifest_path=arguments.manifest,
        summary_output_path=summary_output_path,
        equity_output_path=equity_output_path,
    )

    return EXIT_SUCCESS


def _resolve_portfolio_equity_output_path(
    *,
    summary_output_path: Path,
    equity_output_path: Path | None,
) -> Path:
    """Resolve the combined portfolio equity output path."""
    if equity_output_path is not None:
        return equity_output_path

    return summary_output_path.with_name("portfolio_equity.csv")


def _build_contract_specification(
    arguments: argparse.Namespace,
) -> ContractSpecification | None:
    """Build optional broker contract rules from CLI arguments."""
    values = (
        arguments.contract_size,
        arguments.minimum_lot,
        arguments.maximum_lot,
        arguments.lot_step,
        arguments.below_minimum_lot_policy,
    )

    if all(value is None for value in values):
        return None

    if arguments.contract_size is None:
        raise ValueError("Contract size is required when broker lot sizing options are provided.")

    return ContractSpecification(
        contract_size=arguments.contract_size,
        minimum_lot=(0.01 if arguments.minimum_lot is None else arguments.minimum_lot),
        maximum_lot=(100.0 if arguments.maximum_lot is None else arguments.maximum_lot),
        lot_step=(0.01 if arguments.lot_step is None else arguments.lot_step),
        below_minimum_policy=(
            BelowMinimumLotPolicy.SKIP
            if arguments.below_minimum_lot_policy is None
            else BelowMinimumLotPolicy(arguments.below_minimum_lot_policy)
        ),
    )


def _build_margin_policy(
    arguments: argparse.Namespace,
) -> MarginPolicy | None:
    """Build optional leverage and margin rules from CLI arguments."""
    values = (
        arguments.leverage,
        arguments.insufficient_margin_policy,
    )

    if all(value is None for value in values):
        return None

    if arguments.leverage is None:
        raise ValueError("Leverage is required when margin options are provided.")

    return MarginPolicy(
        leverage=arguments.leverage,
        insufficient_margin_policy=(
            InsufficientMarginPolicy.SKIP
            if arguments.insufficient_margin_policy is None
            else InsufficientMarginPolicy(arguments.insufficient_margin_policy)
        ),
    )


def _resolve_equity_output_path(
    *,
    trade_output_path: Path,
    equity_output_path: Path | None,
) -> Path:
    """
    Resolve the equity CSV output path.

    When no explicit path is supplied, equity.csv is placed
    beside the trade CSV file.
    """
    if equity_output_path is not None:
        return equity_output_path

    return trade_output_path.with_name("equity.csv")


def _load_inputs(
    arguments: argparse.Namespace,
) -> tuple[ScanConfig, list[Candle]]:
    """Load configuration and candle data."""
    config = load_scan_config(arguments.config)

    config = _apply_scan_overrides(
        config,
        extrema_window=arguments.extrema_window,
    )

    candles = load_candles_csv(arguments.csv)

    return config, candles


def _apply_scan_overrides(
    config: ScanConfig,
    *,
    extrema_window: int | None,
) -> ScanConfig:
    """Apply command-line overrides without mutation."""
    if extrema_window is None:
        return config

    return replace(
        config,
        extrema_window=extrema_window,
    )


def _report_error(
    error: Exception,
) -> int:
    """Write a command error to stderr."""
    print(
        f"Error: {error}",
        file=sys.stderr,
    )

    return EXIT_ERROR


def _print_scan_result(
    result: ScanResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> None:
    """Print a human-readable batch scan report."""
    print("NDS scan completed")

    _print_input_summary(
        candle_count=candle_count,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
    )

    print(f"Raw nodes: {len(result.raw_nodes)}")

    print(f"Alternating nodes: {len(result.alternating_nodes)}")

    print(f"Cycles: {len(result.cycles)}")

    print(f"Valid cycles: {len(result.valid_analyses)}")

    print(f"Rejected cycles: {len(result.rejected_analyses)}")

    if not result.analyses:
        print()
        print("No NDS cycles were detected.")
        return

    for number, analysis in enumerate(
        result.analyses,
        start=1,
    ):
        status = "VALID" if analysis.is_valid else "REJECTED"

        print()

        print(f"Cycle {number}: {analysis.cycle.direction.value} | {status}")

        _print_analysis_details(analysis)


def _print_replay_result(
    result: ReplayResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> None:
    """Print a human-readable chronological replay report."""
    print("NDS replay completed")

    _print_input_summary(
        candle_count=candle_count,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
    )

    print(f"Events: {len(result.events)}")

    print(f"Valid events: {len(result.valid_events)}")

    print(f"Rejected events: {len(result.rejected_events)}")

    if not result.events:
        print()
        print("No NDS replay events were detected.")
        return

    for number, event in enumerate(
        result.events,
        start=1,
    ):
        status = "VALID" if event.is_valid else "REJECTED"

        print()

        print(f"Event {number}: {event.analysis.cycle.direction.value} | {status}")

        print(f"Confirmed at index: {event.confirmed_at_index}")

        print(f"Confirmed at time: {event.confirmed_at_time.isoformat()}")

        _print_analysis_details(event.analysis)


def _print_input_summary(
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> None:
    """Print shared candle-input information."""
    print(f"CSV file: {csv_path}")
    print(f"Configuration: {config_path}")
    print(f"Extrema window: {extrema_window}")
    print(f"Candles: {candle_count}")


def _print_backtest_result(
    result: BacktestResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    trade_output_path: Path,
    equity_output_path: Path,
    extrema_window: int,
    execution_policy: ExecutionPolicy,
    account_policy: AccountPolicy,
    cost_policy: TradingCostPolicy,
    contract_specification: ContractSpecification | None,
    margin_policy: MarginPolicy | None,
) -> None:
    """Print a human-readable backtest report."""
    metrics = result.metrics
    execution = result.execution
    account = result.account

    if account is None:
        raise ValueError("Account simulation result is missing.")

    account_metrics = account.metrics

    print("NDS backtest completed")

    _print_input_summary(
        candle_count=candle_count,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
    )

    print(f"Reward-to-risk: {execution_policy.reward_to_risk:.4f}")

    print(f"Stop buffer fraction: {execution_policy.stop_buffer_fraction:.6f}")

    print(f"Intrabar priority: {execution_policy.intrabar_priority.value}")

    print(f"Gap fill mode: {execution_policy.gap_fill_mode.value}")

    print(f"Spread fraction: {cost_policy.spread_fraction:.6f}")

    print(f"Slippage fraction: {cost_policy.slippage_fraction:.6f}")

    print(f"Commission fraction: {cost_policy.commission_fraction:.6f}")

    print(f"Adverse fill fraction: {cost_policy.adverse_fill_fraction:.6f}")

    if contract_specification is None:
        print("Contract sizing: disabled")
    else:
        print("Contract sizing: enabled")
        print(f"Contract size: {contract_specification.contract_size:.8f}")
        print(f"Minimum lot: {contract_specification.minimum_lot:.8f}")
        print(f"Maximum lot: {contract_specification.maximum_lot:.8f}")
        print(f"Lot step: {contract_specification.lot_step:.8f}")
        print(f"Below minimum lot policy: {contract_specification.below_minimum_policy.value}")

    if margin_policy is None:
        print("Margin checking: disabled")
    else:
        print("Margin checking: enabled")
        print(f"Leverage: {margin_policy.leverage:.4f}")
        print(f"Insufficient margin policy: {margin_policy.insufficient_margin_policy.value}")

    print(f"Replay events: {len(result.replay.events)}")

    print(f"Valid events: {len(result.replay.valid_events)}")

    print(f"Signals: {len(result.signals)}")

    print(f"Executed trades: {metrics.trade_count}")

    print(f"Unfilled signals: {len(execution.unfilled_signals)}")

    print(f"Winners: {metrics.winner_count}")
    print(f"Losers: {metrics.loser_count}")
    print(f"Breakeven: {metrics.breakeven_count}")
    print(f"Win rate: {metrics.win_rate:.2%}")
    print(f"Total R: {metrics.total_r:.4f}")
    print(f"Mean R: {metrics.mean_r:.4f}")
    print(f"Best R: {metrics.best_r:.4f}")
    print(f"Worst R: {metrics.worst_r:.4f}")

    print(f"Maximum drawdown: {metrics.maximum_drawdown_r:.4f}R")

    print(f"Total raw price PnL: {metrics.total_price_pnl:.8f}")

    print()
    print("Account simulation")

    print(f"Initial balance: {account_metrics.initial_balance:.2f}")

    print(f"Risk fraction: {account_policy.risk_fraction:.2%}")

    print(f"Overlap policy: {account_policy.overlap_policy.value}")

    print(f"Accepted trades: {account_metrics.accepted_trade_count}")

    print(f"Skipped overlapping trades: {account_metrics.skipped_overlap_count}")

    print(f"Skipped minimum-lot trades: {account_metrics.skipped_minimum_lot_count}")

    print(
        f"Skipped insufficient-margin trades: {account_metrics.skipped_insufficient_margin_count}"
    )

    print(f"Total requested risk: {account_metrics.total_requested_risk:.2f}")

    print(f"Total actual risk: {account_metrics.total_actual_risk:.2f}")

    print(f"Mean risk utilization: {account_metrics.mean_risk_utilization:.2%}")

    print(f"Maximum margin required: {account_metrics.maximum_margin_required:.2f}")

    print(f"Maximum margin utilization: {account_metrics.maximum_margin_utilization:.2%}")

    minimum_free_margin = (
        "N/A"
        if account_metrics.minimum_free_margin_after_entry is None
        else f"{account_metrics.minimum_free_margin_after_entry:.2f}"
    )

    print(f"Minimum free margin after entry: {minimum_free_margin}")

    print(f"Gross filled PnL: {account_metrics.total_gross_pnl:.2f}")

    print(f"Spread/slippage cost: {account_metrics.total_spread_slippage_cost:.2f}")

    print(f"Commission: {account_metrics.total_commission:.2f}")

    print(f"Total trading cost: {account_metrics.total_cost:.2f}")

    print(f"Ending balance: {account_metrics.ending_balance:.2f}")

    print(f"Net profit: {account_metrics.net_profit:.2f}")

    print(f"Account return: {account_metrics.return_fraction:.2%}")

    print(f"Maximum monetary drawdown: {account_metrics.maximum_drawdown_amount:.2f}")

    print(f"Maximum percentage drawdown: {account_metrics.maximum_drawdown_fraction:.2%}")

    print(f"Trade output file: {trade_output_path}")

    print(f"Equity output file: {equity_output_path}")


def _print_holdout_validation_result(
    result: HoldoutValidationResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
    output_path: Path,
) -> None:
    """Print a human-readable holdout validation report."""
    print("NDS holdout validation completed")
    _print_input_summary(
        candle_count=candle_count,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
    )
    print(f"Train fraction: {result.config.train_fraction:.2%}")
    print(f"Split index: {result.split_index}")
    print(f"Split time: {result.split_time.isoformat()}")
    print(f"Boundary trade policy: {result.config.boundary_trade_policy.value}")
    print(f"Boundary trades: {len(result.boundary_trades)}")
    print(f"Excluded boundary trades: {result.excluded_boundary_trade_count}")
    _print_validation_segment(result.train)
    _print_validation_segment(result.test)
    print(f"Output file: {output_path}")


def _print_walk_forward_validation_result(
    result: WalkForwardValidationResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
    output_path: Path,
) -> None:
    """Print a human-readable walk-forward validation report."""
    summary = result.summary
    metrics = summary.test_metrics

    print("NDS walk-forward validation completed")
    _print_input_summary(
        candle_count=candle_count,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
    )
    print(f"Initial train candles: {result.config.initial_train_candles}")
    print(f"Test candles per fold: {result.config.test_candles}")
    print(f"Step candles: {result.config.effective_step_candles}")
    print(f"Folds: {summary.fold_count}")
    print(f"Combined test trades: {metrics.trade_count}")
    print(f"Combined test win rate: {metrics.win_rate:.2%}")
    print(f"Combined test total R: {metrics.total_r:.4f}")
    print(f"Combined test mean R: {metrics.mean_r:.4f}")
    print(f"Combined test maximum drawdown: {metrics.maximum_drawdown_r:.4f}R")
    print(
        "Profitable / losing / flat folds: "
        f"{summary.profitable_fold_count} / "
        f"{summary.losing_fold_count} / "
        f"{summary.flat_fold_count}"
    )
    print(f"Mean independent test return: {summary.mean_test_return_fraction:.2%}")
    print(f"Total independent test net profit: {summary.total_test_net_profit:.2f}")
    print(f"Worst independent test drawdown: {summary.worst_test_drawdown_fraction:.2%}")

    for fold in result.folds:
        print()
        print(
            f"Fold {fold.fold_number}: "
            f"train 0-{fold.train.end_index}, "
            f"test {fold.test.start_index}-{fold.test.end_index}"
        )
        print(
            "Test trades / Total R / Win rate: "
            f"{fold.test.metrics.trade_count} / "
            f"{fold.test.metrics.total_r:.4f} / "
            f"{fold.test.metrics.win_rate:.2%}"
        )

    print(f"Output file: {output_path}")


def _print_validation_segment(
    segment: ValidationSegment,
) -> None:
    """Print one holdout train or test segment."""
    print()
    print(f"{segment.name} segment: indexes {segment.start_index}-{segment.end_index}")
    print(f"Candles: {segment.candle_count}")
    print(f"Trades: {segment.metrics.trade_count}")
    print(f"Win rate: {segment.metrics.win_rate:.2%}")
    print(f"Total R: {segment.metrics.total_r:.4f}")
    print(f"Mean R: {segment.metrics.mean_r:.4f}")

    if segment.account is not None:
        print(f"Ending balance: {segment.account.metrics.ending_balance:.2f}")
        print(f"Account return: {segment.account.metrics.return_fraction:.2%}")


def _print_portfolio_result(
    result: PortfolioResult,
    *,
    manifest_path: Path,
    summary_output_path: Path,
    equity_output_path: Path,
) -> None:
    """Print a human-readable portfolio report."""
    metrics = result.metrics

    print("NDS portfolio backtest completed")
    print(f"Manifest: {manifest_path}")
    print(f"Datasets: {metrics.dataset_count}")
    print(f"Total candles: {metrics.total_candle_count}")
    print(f"Total signals: {metrics.total_signal_count}")
    print(f"Executed trades: {metrics.total_executed_trade_count}")
    print(f"Accepted trades: {metrics.total_accepted_trade_count}")
    print(f"Skipped overlapping trades: {metrics.total_skipped_overlap_count}")
    print(f"Skipped minimum-lot trades: {metrics.total_skipped_minimum_lot_count}")
    print(f"Skipped insufficient-margin trades: {metrics.total_skipped_margin_count}")
    print(f"Profitable datasets: {metrics.profitable_dataset_count}")
    print(f"Losing datasets: {metrics.losing_dataset_count}")
    print(f"Flat datasets: {metrics.flat_dataset_count}")
    print(f"Initial balance: {metrics.initial_balance:.2f}")
    print(f"Ending balance: {metrics.ending_balance:.2f}")
    print(f"Net profit: {metrics.net_profit:.2f}")
    print(f"Portfolio return: {metrics.return_fraction:.2%}")
    print(f"Mean dataset return: {metrics.mean_dataset_return_fraction:.2%}")
    print(f"Total trading cost: {metrics.total_cost:.2f}")
    print(
        "Maximum portfolio drawdown: "
        f"{metrics.maximum_drawdown_amount:.2f} "
        f"({metrics.maximum_drawdown_fraction:.2%})"
    )
    print(f"Summary output file: {summary_output_path}")
    print(f"Equity output file: {equity_output_path}")

    print()
    print("Dataset allocation")

    for dataset_result in result.datasets:
        dataset = dataset_result.dataset
        print(
            f"{dataset.dataset_id}: "
            f"{dataset.symbol} {dataset.timeframe} | "
            f"weight={dataset_result.normalized_weight:.2%} | "
            f"allocated={dataset_result.allocated_balance:.2f} | "
            f"ending={dataset_result.ending_balance:.2f} | "
            f"return={dataset_result.return_fraction:.2%}"
        )


def _print_analysis_details(
    analysis: CycleAnalysis,
) -> None:
    """Print nodes, legs, and quality of one cycle."""
    node_summary = " -> ".join(_format_node(node) for node in analysis.cycle.nodes)

    print(f"Nodes: {node_summary}")

    legs_summary = ", ".join(
        f"Delta{index}={value:.8f}"
        for index, value in enumerate(
            analysis.legs.values,
            start=1,
        )
    )

    print(f"Legs: {legs_summary}")

    print(
        "Quality: "
        f"Hook1="
        f"{analysis.quality.hook_ratios.first:.6f}, "
        f"Hook2="
        f"{analysis.quality.hook_ratios.second:.6f}, "
        f"NSI="
        f"{analysis.quality.nsi.score:.6f}"
    )

    if analysis.rejection_reasons:
        print("Rejection reasons: " + ", ".join(analysis.rejection_reasons))


def _format_node(
    node: Node,
) -> str:
    """Format one labeled NDS cycle node."""
    label_text = node.label.value if node.label is not None else "UNKNOWN"

    return f"{label_text}={node.price:.5f}"


if __name__ == "__main__":
    raise SystemExit(main())
