import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class StoreConfig:
    type: str
    tcin: str = ""
    store_id: str = ""
    zip: str = ""


@dataclass
class ProductConfig:
    name: str
    stores: list[StoreConfig] = field(default_factory=list)


@dataclass
class PollingConfig:
    base_interval_seconds: int = 900
    jitter_factor: float = 0.5


@dataclass
class NotificationConfig:
    type: str
    recipients: list[str] = field(default_factory=list)


@dataclass
class Config:
    products: list[ProductConfig] = field(default_factory=list)
    polling: PollingConfig = field(default_factory=PollingConfig)
    notifications: list[NotificationConfig] = field(default_factory=list)
    log_file: str | None = None
    log_level: str = "INFO"
    once: bool = False
    proxy_url: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stock_checker",
        description="Monitor product availability at retail stores",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Base polling interval in seconds (overrides config)",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=None,
        help="Jitter factor 0.0–1.0 (overrides config)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Path to write logs (default: stdout)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=False,
        help="Run all checks once and exit",
    )
    return parser.parse_args(argv)


def load_config(argv: list[str] | None = None) -> Config:
    args = parse_args(argv)

    # Load YAML config
    config_path = Path(args.config)
    yaml_data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f) or {}
    else:
        logger.warning("Config file %s not found, using defaults", config_path)

    # Build products
    products: list[ProductConfig] = []
    for p in yaml_data.get("products", []):
        stores = [StoreConfig(**s) for s in p.get("stores", [])]
        products.append(ProductConfig(name=p["name"], stores=stores))

    # Build polling config (YAML defaults, CLI overrides)
    polling_data = yaml_data.get("polling", {})
    polling = PollingConfig(
        base_interval_seconds=polling_data.get("base_interval_seconds", 900),
        jitter_factor=polling_data.get("jitter_factor", 0.5),
    )
    if args.interval is not None:
        polling.base_interval_seconds = args.interval
    if args.jitter is not None:
        polling.jitter_factor = args.jitter

    # Build notification configs
    notifications: list[NotificationConfig] = []
    for n in yaml_data.get("notifications", []):
        notifications.append(
            NotificationConfig(
                type=n["type"],
                recipients=n.get("recipients", []),
            )
        )
    # Always ensure log notifier is present
    if not any(n.type == "log" for n in notifications):
        notifications.insert(0, NotificationConfig(type="log"))

    # Remaining settings: CLI overrides YAML overrides defaults
    log_file = args.log_file or yaml_data.get("log_file")
    log_level = args.log_level or yaml_data.get("log_level", "INFO")

    # Optional proxy
    proxy_data = yaml_data.get("proxy", {})
    proxy_url = proxy_data.get("url") if proxy_data else None

    return Config(
        products=products,
        polling=polling,
        notifications=notifications,
        log_file=log_file,
        log_level=log_level,
        once=args.once,
        proxy_url=proxy_url,
    )
