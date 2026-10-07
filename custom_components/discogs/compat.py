"""Pick the schema library the running Home Assistant release expects.

Home Assistant is replacing voluptuous with probatio, and the switch lands
in stages:

- up to 2026.8: voluptuous everywhere
- 2026.9: config_validation and PLATFORM_SCHEMA are probatio, config/options
  flow forms are still voluptuous
- 2026.10+: probatio everywhere, and voluptuous is no longer a Home
  Assistant dependency (it is only installed transitively, if at all)

Rather than guessing from version numbers, each schema is built with the
same library Home Assistant itself uses for that job.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from homeassistant import data_entry_flow
from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA


def _flow_schema_lib() -> ModuleType:
    """Return the library data_entry_flow validates form schemas with."""
    lib = getattr(data_entry_flow, "probatio", None) or getattr(
        data_entry_flow, "vol", None
    )
    if lib is None:  # pragma: no cover - defensive, should never happen
        lib = importlib.import_module("voluptuous")
    return lib


def _platform_schema_lib() -> ModuleType:
    """Return the library the sensor PLATFORM_SCHEMA is built with."""
    package = type(SENSOR_PLATFORM_SCHEMA).__module__.partition(".")[0]
    return importlib.import_module(package)


flow_vol: ModuleType = _flow_schema_lib()
platform_vol: ModuleType = _platform_schema_lib()
