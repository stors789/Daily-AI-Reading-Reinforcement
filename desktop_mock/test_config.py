"""Manual credential-free config-store smoke check.

This module used to print complete loaded configurations and write a literal
API key.  Keeping it import-safe prevents accidental secret disclosure when a
test collector or developer runs the desktop diagnostics directory.
"""

from desktop_adapters import DesktopConfigAdapter


def config_store_is_readable() -> bool:
    config = DesktopConfigAdapter().load()
    return isinstance(config, dict)


if __name__ == "__main__":
    raise SystemExit(0 if config_store_is_readable() else 1)
