from pathlib import Path

import pytest

from nds_bot.settings import (
    ConfigurationError,
    load_scan_config,
    load_settings,
)


def write_config(
    path: Path,
    content: str,
) -> Path:
    path.write_text(
        content,
        encoding="utf-8",
    )

    return path


def test_loads_valid_settings(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        """
topology:
  extrema_window: 8

quality:
  hook_ideal: 0.86
  hook_minimum: 0.30
  hook_maximum: 0.90
  maximum_nsi: 0.50
""".strip(),
    )

    settings = load_settings(config_path)

    assert settings.topology.extrema_window == 8
    assert settings.quality.hook_ideal == pytest.approx(0.86)
    assert settings.quality.hook_minimum == pytest.approx(0.30)
    assert settings.quality.hook_maximum == pytest.approx(0.90)
    assert settings.quality.maximum_nsi == pytest.approx(0.50)


def test_settings_convert_to_scan_config(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        """
topology:
  extrema_window: 7

quality:
  hook_ideal: 0.86
  hook_minimum: 0.25
  hook_maximum: 0.92
  maximum_nsi: 0.60
""".strip(),
    )

    scan_config = load_scan_config(config_path)

    assert scan_config.extrema_window == 7
    assert scan_config.quality_thresholds.hook_ideal == pytest.approx(0.86)
    assert scan_config.quality_thresholds.maximum_nsi == pytest.approx(0.60)


def test_empty_yaml_uses_defaults(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        "",
    )

    settings = load_settings(config_path)

    assert settings.topology.extrema_window == 6
    assert settings.quality.hook_ideal == pytest.approx(0.86)
    assert settings.quality.maximum_nsi == pytest.approx(0.60)


def test_missing_configuration_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(
        ConfigurationError,
        match="Configuration file does not exist",
    ):
        load_settings(missing_path)


def test_non_mapping_configuration_is_rejected(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        """
- topology
- quality
""".strip(),
    )

    with pytest.raises(
        ConfigurationError,
        match="Configuration root must be a YAML mapping",
    ):
        load_settings(config_path)


def test_unknown_configuration_key_is_rejected(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        """
topology:
  extream_window: 6
""".strip(),
    )

    with pytest.raises(
        ConfigurationError,
        match="Invalid configuration",
    ):
        load_settings(config_path)


def test_invalid_hook_range_is_rejected(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        """
quality:
  hook_ideal: 0.86
  hook_minimum: 0.90
  hook_maximum: 0.50
  maximum_nsi: 0.60
""".strip(),
    )

    with pytest.raises(
        ConfigurationError,
        match="Invalid configuration",
    ):
        load_settings(config_path)
