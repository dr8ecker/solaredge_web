"""Read Supervisor options without printing credentials or supplied values."""

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigurationError(ValueError):
    pass


def validate_url(value: str, name: str, *, optional: bool = False) -> None:
    if optional and not value:
        return
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise ConfigurationError(f"{name}: invalid URL") from None
    # HTTP is allowed only on loopback for the local browser integration test.
    loopback = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (url.scheme != "https" and not (url.scheme == "http" and loopback)) or not url.hostname:
        raise ConfigurationError(f"{name}: HTTPS URL required")
    if url.username or url.password or url.query or url.fragment:
        raise ConfigurationError(f"{name}: credentials, query and fragment are not allowed")
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError(f"{name}: invalid port")


@dataclass(frozen=True)
class Config:
    solar_edge_username: str = field(default="", repr=False)
    solar_edge_password: str = field(default="", repr=False)
    plant_name: str = "Spaeth"
    poll_interval: int = 1800
    headless: bool = True
    debug: bool = False
    mode: str = "normal"
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_discovery_prefix: str = "homeassistant"
    mqtt_username: str = field(default="", repr=False)
    mqtt_password: str = field(default="", repr=False)
    login_url: str = ""
    monitoring_url: str = "https://monitoring.solaredge.com/"
    browser_path: str = ""
    page_timeout: int = 30000
    max_retries: int = 5
    site_timezone: str = "Europe/Berlin"
    history_days: int = 7
    history_import: bool = True
    data_dir: Path = field(default=Path("/data/runtime"), repr=False)

    @property
    def storage_state_path(self) -> Path:
        return self.data_dir / "solaredge_storage_state.json"

    @property
    def health_max_age(self) -> int:
        return max(900, self.poll_interval * 3, self.page_timeout // 1000 * 2)

    @classmethod
    def load(cls, path: Path, *, data_dir: Path = Path("/data/runtime")) -> "Config":
        try:
            values = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ConfigurationError("Cannot read a valid options.json") from None
        if not isinstance(values, dict):
            raise ConfigurationError("options.json must be a JSON object")
        allowed = {item.name for item in fields(cls)} - {"data_dir"}
        if set(values) - allowed:
            raise ConfigurationError("options.json contains unsupported option names")
        defaults = cls()
        for key, value in values.items():
            if type(value) is not type(getattr(defaults, key)):
                raise ConfigurationError(f"{key}: wrong value type")
        config = cls(**values, data_dir=data_dir)
        for key, low, high in (
            ("poll_interval", 30, 3600), ("mqtt_port", 1, 65535),
            ("page_timeout", 5000, 120000), ("max_retries", 1, 10),
            ("history_days", 1, 31),
        ):
            if not low <= getattr(config, key) <= high:
                raise ConfigurationError(f"{key}: must be between {low} and {high}")
        if config.mode not in {"smoke_test", "discovery", "normal"}:
            raise ConfigurationError("mode: expected normal, discovery or smoke_test")
        if not config.plant_name.strip():
            raise ConfigurationError("plant_name: required")
        if not config.mqtt_discovery_prefix or any(c in config.mqtt_discovery_prefix for c in '+#\x00'):
            raise ConfigurationError("mqtt_discovery_prefix: invalid topic")
        try:
            ZoneInfo(config.site_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigurationError("site_timezone: unknown timezone") from None
        validate_url(config.monitoring_url, "monitoring_url")
        validate_url(config.login_url, "login_url", optional=True)
        if config.browser_path and not Path(config.browser_path).is_file():
            raise ConfigurationError("browser_path: executable file not found")
        return config
