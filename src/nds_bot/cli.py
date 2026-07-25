import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from nds_bot.data.csv_loader import (
    CandleCsvError,
    load_candles_csv,
)
from nds_bot.models import Node
from nds_bot.pipeline import (
    ScanConfig,
    ScanResult,
    scan_candles,
)
from nds_bot.settings import (
    ConfigurationError,
    load_scan_config,
)

EXIT_SUCCESS = 0
EXIT_ERROR = 1


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
        help="Scan a candle CSV file for NDS cycles.",
    )

    scan_parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to the candle CSV file.",
    )

    scan_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default.yaml"),
        help=("Path to the YAML configuration file (default: config/default.yaml)."),
    )

    scan_parser.add_argument(
        "--extrema-window",
        type=int,
        default=None,
        help=("Override the extrema window defined in the YAML configuration."),
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the NDS command-line interface.

    Returns:
        0 when execution succeeds.
        1 when configuration, CSV, or processing fails.
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "scan":
        return _run_scan(arguments)

    parser.error(f"Unsupported command: {arguments.command}")

    return EXIT_ERROR


def _run_scan(arguments: argparse.Namespace) -> int:
    """Load inputs, execute the pipeline, and print the result."""
    try:
        config = load_scan_config(arguments.config)

        config = _apply_scan_overrides(
            config,
            extrema_window=arguments.extrema_window,
        )

        candles = load_candles_csv(arguments.csv)

        result = scan_candles(
            candles,
            config=config,
        )

    except (
        ConfigurationError,
        CandleCsvError,
        ValueError,
    ) as error:
        print(
            f"Error: {error}",
            file=sys.stderr,
        )

        return EXIT_ERROR

    _print_scan_result(
        result,
        candle_count=len(candles),
        csv_path=arguments.csv,
        config_path=arguments.config,
        extrema_window=config.extrema_window,
    )

    return EXIT_SUCCESS


def _apply_scan_overrides(
    config: ScanConfig,
    *,
    extrema_window: int | None,
) -> ScanConfig:
    """Apply command-line overrides without mutating the config."""
    if extrema_window is None:
        return config

    return replace(
        config,
        extrema_window=extrema_window,
    )


def _print_scan_result(
    result: ScanResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> None:
    """Print a human-readable summary of the scan result."""
    print("NDS scan completed")
    print(f"CSV file: {csv_path}")
    print(f"Configuration: {config_path}")
    print(f"Extrema window: {extrema_window}")
    print(f"Candles: {candle_count}")
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
