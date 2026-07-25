import json
from collections.abc import Mapping
from pathlib import Path

from nds_bot.pipeline import CycleAnalysis, ScanResult
from nds_bot.replay import ReplayResult


def build_scan_report(
    result: ScanResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> dict[str, object]:
    """Convert a batch scan result to a JSON-compatible dictionary."""
    return {
        "mode": "scan",
        "input": {
            "csv_file": str(csv_path),
            "config_file": str(config_path),
            "extrema_window": extrema_window,
            "candle_count": candle_count,
        },
        "summary": {
            "raw_nodes": len(result.raw_nodes),
            "alternating_nodes": len(result.alternating_nodes),
            "cycles": len(result.cycles),
            "valid_cycles": len(result.valid_analyses),
            "rejected_cycles": len(result.rejected_analyses),
        },
        "cycles": [_analysis_to_dict(analysis) for analysis in result.analyses],
    }


def build_replay_report(
    result: ReplayResult,
    *,
    candle_count: int,
    csv_path: Path,
    config_path: Path,
    extrema_window: int,
) -> dict[str, object]:
    """Convert a replay result to a JSON-compatible dictionary."""
    return {
        "mode": "replay",
        "input": {
            "csv_file": str(csv_path),
            "config_file": str(config_path),
            "extrema_window": extrema_window,
            "candle_count": candle_count,
        },
        "summary": {
            "events": len(result.events),
            "valid_events": len(result.valid_events),
            "rejected_events": len(result.rejected_events),
        },
        "events": [
            {
                "confirmed_at_index": event.confirmed_at_index,
                "confirmed_at_time": (event.confirmed_at_time.isoformat()),
                "analysis": _analysis_to_dict(event.analysis),
            }
            for event in result.events
        ],
    }


def render_json(report: Mapping[str, object]) -> str:
    """Render a report as formatted JSON text."""
    return json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )


def _analysis_to_dict(
    analysis: CycleAnalysis,
) -> dict[str, object]:
    cycle = analysis.cycle
    quality = analysis.quality
    hook_ratios = quality.hook_ratios
    nsi = quality.nsi

    return {
        "direction": cycle.direction.value,
        "valid": analysis.is_valid,
        "rejection_reasons": list(analysis.rejection_reasons),
        "nodes": [
            {
                "label": (node.label.value if node.label is not None else None),
                "index": node.index,
                "time": node.time.isoformat(),
                "price": node.price,
                "node_type": node.node_type.value,
            }
            for node in cycle.nodes
        ],
        "legs": {
            "delta_1": analysis.legs.delta_1,
            "delta_2": analysis.legs.delta_2,
            "delta_3": analysis.legs.delta_3,
            "delta_4": analysis.legs.delta_4,
            "delta_5": analysis.legs.delta_5,
        },
        "quality": {
            "hook_1": hook_ratios.first,
            "hook_2": hook_ratios.second,
            "hook_mean": hook_ratios.mean,
            "nsi": nsi.score,
            "nsi_comparison_differences": list(nsi.comparison_differences),
            "mean_leg_magnitude": nsi.mean_leg_magnitude,
            "mean_comparison_difference": (nsi.mean_comparison_difference),
            "first_hook_valid": quality.first_hook_valid,
            "second_hook_valid": quality.second_hook_valid,
            "hooks_valid": quality.hooks_valid,
            "nsi_valid": quality.nsi_valid,
        },
    }
