from collections.abc import Mapping
from pathlib import Path
from typing import Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from nds_bot.pipeline import ScanConfig
from nds_bot.quality.validation import QualityThresholds


class ConfigurationError(ValueError):
    """Raised when an application configuration cannot be loaded."""


class TopologySettings(BaseModel):
    """Configuration for local-extrema detection."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    extrema_window: int = Field(
        default=6,
        ge=1,
    )


class QualitySettings(BaseModel):
    """Configuration for Hook Ratio and NSI validation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    hook_ideal: float = Field(
        default=0.86,
        ge=0,
    )
    hook_minimum: float = Field(
        default=0.25,
        ge=0,
    )
    hook_maximum: float = Field(
        default=0.92,
        ge=0,
    )
    maximum_nsi: float = Field(
        default=0.60,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_hook_range(self) -> Self:
        if self.hook_maximum < self.hook_minimum:
            raise ValueError("hook_maximum cannot be below hook_minimum.")

        if not self.hook_minimum <= self.hook_ideal <= self.hook_maximum:
            raise ValueError("hook_ideal must be inside the accepted hook range.")

        return self


class AppSettings(BaseModel):
    """Complete application configuration loaded from YAML."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    topology: TopologySettings = Field(default_factory=TopologySettings)
    quality: QualitySettings = Field(default_factory=QualitySettings)

    def to_scan_config(self) -> ScanConfig:
        """Convert YAML settings to the pipeline configuration."""
        return ScanConfig(
            extrema_window=self.topology.extrema_window,
            quality_thresholds=QualityThresholds(
                hook_ideal=self.quality.hook_ideal,
                hook_minimum=self.quality.hook_minimum,
                hook_maximum=self.quality.hook_maximum,
                maximum_nsi=self.quality.maximum_nsi,
            ),
        )


def load_settings(path: str | Path) -> AppSettings:
    """Load and validate application settings from a YAML file."""
    config_path = Path(path)

    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {config_path}")

    try:
        content = config_path.read_text(encoding="utf-8")
        raw_data = yaml.safe_load(content)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Could not read configuration file: {config_path}") from error

    if raw_data is None:
        raw_data = {}

    if not isinstance(raw_data, Mapping):
        raise ConfigurationError("Configuration root must be a YAML mapping.")

    try:
        return AppSettings.model_validate(dict(raw_data))
    except ValidationError as error:
        raise ConfigurationError(f"Invalid configuration: {error}") from error


def load_scan_config(path: str | Path) -> ScanConfig:
    """Load a YAML file and return pipeline-ready settings."""
    return load_settings(path).to_scan_config()
