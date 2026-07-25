import csv
from collections.abc import Sequence
from pathlib import Path

from nds_bot.signals import TradeSignal

SIGNAL_COLUMNS = (
    "generated_at_index",
    "generated_at_time",
    "side",
    "reference_price",
    "cycle_direction",
    "z_index",
    "n1_index",
    "s1_index",
    "n2_index",
    "s2_index",
    "n3_index",
    "n3_price",
    "hook_1",
    "hook_2",
    "nsi",
)


class SignalCsvError(ValueError):
    """Raised when a signal CSV file cannot be written."""


def write_signals_csv(
    signals: Sequence[TradeSignal],
    path: str | Path,
) -> Path:
    """
    Write generated trade signals to a CSV file.

    An empty signal collection still creates a CSV containing
    the header row.
    """
    output_path = Path(path)

    try:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=SIGNAL_COLUMNS,
            )

            writer.writeheader()

            for signal in signals:
                writer.writerow(_signal_to_row(signal))

    except OSError as error:
        raise SignalCsvError(f"Could not write signal CSV file: {output_path}") from error

    return output_path


def _signal_to_row(
    signal: TradeSignal,
) -> dict[str, object]:
    cycle = signal.analysis.cycle
    quality = signal.analysis.quality

    return {
        "generated_at_index": signal.generated_at_index,
        "generated_at_time": (signal.generated_at_time.isoformat()),
        "side": signal.side.value,
        "reference_price": signal.reference_price,
        "cycle_direction": signal.cycle_direction.value,
        "z_index": cycle.z.index,
        "n1_index": cycle.n1.index,
        "s1_index": cycle.s1.index,
        "n2_index": cycle.n2.index,
        "s2_index": cycle.s2.index,
        "n3_index": cycle.n3.index,
        "n3_price": cycle.n3.price,
        "hook_1": quality.hook_ratios.first,
        "hook_2": quality.hook_ratios.second,
        "nsi": quality.nsi.score,
    }
