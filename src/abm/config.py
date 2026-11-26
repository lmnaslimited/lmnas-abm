"""Non-secret TOML configuration for regional package preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 installs
        tomllib = None  # type: ignore[assignment]


DEFAULT_CONFIG_PATH = Path("config/abm.toml")
SECRET_KEY_FRAGMENTS = ("api_key", "api_secret", "password", "token", "credential", "secret")


class ConfigurationError(ValueError):
    """Safe-to-display configuration error; never includes configuration values."""


@dataclass(frozen=True)
class ABMConfig:
    organization_assessment_template: str | None
    regional_territory: str | None
    package_output_dir: Path | None


def _contains_secret_key(value: Any, prefix: str = "") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if any(fragment in str(key).lower() for fragment in SECRET_KEY_FRAGMENTS):
                return path
            found = _contains_secret_key(child, path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _contains_secret_key(child, f"{prefix}[{index}]")
            if found:
                return found
    return None


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> ABMConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}. Create it from config/abm.example.toml."
        )
    if tomllib is None:
        raise ConfigurationError("TOML support is unavailable; install the Python 3.10 tomli dependency")
    try:
        with config_path.open("rb") as stream:
            data = tomllib.load(stream)
    except Exception as exc:
        # Parser exceptions can quote malformed source text. Keep values private.
        raise ConfigurationError(f"Configuration file is not valid TOML: {config_path}") from exc
    secret_key = _contains_secret_key(data)
    if secret_key:
        raise ConfigurationError(f"Credentials are not allowed in ABM configuration (field {secret_key})")
    if not isinstance(data, dict) or set(data) - {"defaults"}:
        raise ConfigurationError("Configuration may contain only a [defaults] section")
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigurationError("[defaults] must be a TOML table")
    allowed = {"organization_assessment_template", "regional_territory", "package_output_dir"}
    unknown = sorted(set(defaults) - allowed)
    if unknown:
        raise ConfigurationError(f"Unknown configuration field(s): {', '.join(unknown)}")

    def optional_text(key: str) -> str | None:
        value = defaults.get(key)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ConfigurationError(f"Configuration field {key} must be a string")
        return value.strip() or None

    output = optional_text("package_output_dir")
    return ABMConfig(
        organization_assessment_template=optional_text("organization_assessment_template"),
        regional_territory=optional_text("regional_territory"),
        package_output_dir=Path(output) if output else None,
    )
