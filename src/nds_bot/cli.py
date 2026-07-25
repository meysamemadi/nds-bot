import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from nds_bot.data.csv_loader import (
    CandleCsvError,
    load_candles_csv,
)
from nds_bot.models import Candle, Node
from nds_bot.pipeline import (
    CycleAnalysis,
    ScanConfig,
    ScanResult,
    scan_candles,
)
from nds_bot.replay import ReplayResult, replay_candles
from nds_bot.reporting import (
    build_replay_report,
    build_scan_report,
    render_json,
)
from nds_bot.settings import (
    ConfigurationError,
    load_scan_config,
)

EXIT_SUCCESS = 0
EXIT_ERROR = 1

OUTPUT_FORMATS = (
    "text",
    "json",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the NDS command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="nds-bot",
        description=("Detect and evaluate NDS cycles in candle CSV data."),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a complete candle CSV file.",
    )

    _add_common_arguments(scan_parser)

    replay_parser = subparsers.add_parser(
        "replay",
        help=("Replay candles chronologically without look-ahead bias."),
    )

    _add_common_arguments(replay_parser)

    return parser


def _add_common_arguments(
    parser: argparse.ArgumentParser,
) -> None:
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

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=OUTPUT_FORMATS,
        default="text",
        help="Output format: text or json.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the NDS command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "scan":
        return _run_scan(arguments)

    if arguments.command == "replay":
        return _run_replay(arguments)

    parser.error(f"Unsupported command: {arguments.command}")

    return EXIT_ERROR


def _run_scan(arguments: argparse.Namespace) -> int:
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


def _run_replay(arguments: argparse.Namespace) -> int:
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


def _load_inputs(
    arguments: argparse.Namespace,
) -> tuple[ScanConfig, list[Candle]]:
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


def _report_error(error: Exception) -> int:
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
    print(f"CSV file: {csv_path}")
    print(f"Configuration: {config_path}")
    print(f"Extrema window: {extrema_window}")
    print(f"Candles: {candle_count}")


def _print_analysis_details(
    analysis: CycleAnalysis,
) -> None:
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


def _format_node(node: Node) -> str:
    """Format one labeled NDS cycle node."""
    label_text = node.label.value if node.label is not None else "UNKNOWN"

    return f"{label_text}={node.price:.5f}"


if __name__ == "__main__":
    raise SystemExit(main())
