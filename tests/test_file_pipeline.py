from pathlib import Path

from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import scan_candles
from nds_bot.settings import load_scan_config


def test_yaml_and_csv_can_run_complete_pipeline(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.yaml"
    csv_path = tmp_path / "candles.csv"

    config_path.write_text(
        """
topology:
  extrema_window: 1

quality:
  hook_ideal: 0.86
  hook_minimum: 0.25
  hook_maximum: 0.92
  maximum_nsi: 0.60
""".strip(),
        encoding="utf-8",
    )

    csv_path.write_text(
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,1.08100,1.08100,1.08100,1.08100,1000
2026-01-01T01:00:00Z,1.08000,1.08000,1.08000,1.08000,1000
2026-01-01T02:00:00Z,1.08300,1.08300,1.08300,1.08300,1000
2026-01-01T03:00:00Z,1.08650,1.08650,1.08650,1.08650,1000
2026-01-01T04:00:00Z,1.08400,1.08400,1.08400,1.08400,1000
2026-01-01T05:00:00Z,1.08230,1.08230,1.08230,1.08230,1000
2026-01-01T06:00:00Z,1.08600,1.08600,1.08600,1.08600,1000
2026-01-01T07:00:00Z,1.09100,1.09100,1.09100,1.09100,1000
2026-01-01T08:00:00Z,1.08800,1.08800,1.08800,1.08800,1000
2026-01-01T09:00:00Z,1.08600,1.08600,1.08600,1.08600,1000
2026-01-01T10:00:00Z,1.09000,1.09000,1.09000,1.09000,1000
2026-01-01T11:00:00Z,1.09480,1.09480,1.09480,1.09480,1000
2026-01-01T12:00:00Z,1.09200,1.09200,1.09200,1.09200,1000
""".strip(),
        encoding="utf-8",
    )

    scan_config = load_scan_config(config_path)
    candles = load_candles_csv(csv_path)

    result = scan_candles(
        candles,
        config=scan_config,
    )

    assert len(result.cycles) == 1
    assert len(result.valid_analyses) == 1
    assert result.valid_analyses[0].is_valid is True
