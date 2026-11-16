"""Register map of the Husdata H66 Modbus TCP server.

The H66 numbers its Modbus registers sequentially, one per parameter shown on
its web page, in the order of that page. The address therefore depends on the
heat pump controller, the H66 firmware, and any custom registers added in the
H66. Read-only parameters are INPUT registers (FC04), writable parameters are
HOLDING registers (FC03/FC06). Every register is a signed 16-bit value.

Each parameter also has a Husdata variable ID ("Idx", four hex digits such as
``0007`` or ``1A01``). Its first digit tells the value type, which gives the
default scaling (see ``VariableKind``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class VariableKind(StrEnum):
    """Value type of a Husdata variable, from the first digit of its ID."""

    TEMPERATURE = "temperature"  # 0xxx, 0.1 °C
    STATUS = "status"  # 1xxx, 0/1
    NUMBER = "number"  # 2xxx, 0.1
    PERCENT = "percent"  # 3xxx, 0.1 %
    ENERGY = "energy"  # 5xxx, 0.1 kWh
    HOURS = "hours"  # 6xxx, h
    MINUTES = "minutes"  # 7xxx, min
    INTEGER = "integer"  # Bxxx
    POWER = "power"  # Cxxx, W
    OTHER = "other"


# Default (scale, unit) per kind. Verified against a Rego 600 and its H66 web
# page; kinds without an example there follow the same Husdata convention.
_KIND_DEFAULTS: dict[VariableKind, tuple[float, str | None]] = {
    VariableKind.TEMPERATURE: (0.1, "°C"),
    VariableKind.STATUS: (1, None),
    VariableKind.NUMBER: (0.1, None),
    VariableKind.PERCENT: (0.1, "%"),
    VariableKind.ENERGY: (0.1, "kWh"),
    VariableKind.HOURS: (1, "h"),
    VariableKind.MINUTES: (1, "min"),
    VariableKind.INTEGER: (1, None),
    VariableKind.POWER: (1, "W"),
    VariableKind.OTHER: (1, None),
}

_KIND_BY_DIGIT: dict[str, VariableKind] = {
    "0": VariableKind.TEMPERATURE,
    "1": VariableKind.STATUS,
    "2": VariableKind.NUMBER,
    "3": VariableKind.PERCENT,
    "5": VariableKind.ENERGY,
    "6": VariableKind.HOURS,
    "7": VariableKind.MINUTES,
    "B": VariableKind.INTEGER,
    "C": VariableKind.POWER,
}

# Raw value the H66 reports for a temperature sensor that is not connected
# (-48.3 °C, as an unsigned 16-bit pattern).
NO_SENSOR = 0xFE1D

# The H66 answers at most 20 registers per request.
MAX_REGISTERS_PER_REQUEST = 20


def kind_from_variable_id(variable_id: str) -> VariableKind:
    """Return the value type encoded in the first digit of a variable ID."""
    return _KIND_BY_DIGIT.get(variable_id[:1].upper(), VariableKind.OTHER)


@dataclass(frozen=True, kw_only=True)
class Register:
    """One H66 parameter and where it lives in the Modbus register table."""

    key: str
    """Stable snake_case name used by this library."""

    variable_id: str
    """Husdata variable ID ("Idx"), four upper-case hex digits."""

    address: int
    """Modbus register address (0-based)."""

    name: str
    """Name as shown on the H66 web page."""

    writable: bool = False
    """HOLDING register that can be written, otherwise a read-only INPUT one."""

    kind: VariableKind
    scale: float
    """Multiply the raw register value by this to get the value in ``unit``."""

    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[int, ...] | None = None
    """The only values the setting accepts, when they aren't a plain range."""

    write_only: bool = False
    """The value read back means nothing (Husdata: "no read")."""

    @property
    def signed(self) -> bool:
        """Whether the raw value is a signed 16-bit integer.

        Temperatures and numbers (e.g. the heat curve parallel offset) can be
        negative. Counters, power and energy are unsigned: operating hours
        pass 32767 h on an older heat pump.
        """
        return self.kind in (VariableKind.TEMPERATURE, VariableKind.NUMBER)

    @property
    def space(self) -> str:
        """Modbus register space: ``"holding"`` or ``"input"``."""
        return "holding" if self.writable else "input"


@dataclass(frozen=True, kw_only=True)
class _Known:
    """What this library knows about a Husdata variable, apart from its address."""

    key: str
    scale: float | None = None
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[int, ...] | None = None
    write_only: bool = False


# Husdata variables this library knows by ID. Ranges and meanings come from
# Husdata's "IVT Rego 600 / 637 Controllers" variable list for the H66
# (https://online.husdata.se/h-docs/C00.pdf, 2026-01-14).
KNOWN_VARIABLES: dict[str, _Known] = {
    # Temperatures
    "0001": _Known(key="radiator_return"),
    "0002": _Known(key="radiator_forward"),
    "0003": _Known(key="heat_carrier_return"),
    "0004": _Known(key="heat_carrier_forward"),
    "0005": _Known(key="brine_in"),
    "0006": _Known(key="brine_out"),
    "0007": _Known(key="outdoor"),
    "0008": _Known(key="indoor"),
    "0009": _Known(key="hot_water_top"),
    "000A": _Known(key="hot_water_mid"),
    "000B": _Known(key="hot_gas"),
    "0107": _Known(key="heating_setpoint"),
    "0111": _Known(key="hot_water_setpoint"),
    # Status
    "3104": _Known(key="add_heat_status"),
    "1A01": _Known(key="compressor"),
    "1A02": _Known(key="add_heat_step_1"),
    "1A03": _Known(key="add_heat_step_2"),
    "1A04": _Known(key="pump_cold_circuit"),
    "1A05": _Known(key="pump_heat_circuit"),
    "1A06": _Known(key="pump_radiator"),
    # Off: radiator heating, on: hot water production.
    "1A07": _Known(key="switch_valve_1"),
    "1A20": _Known(key="alarm"),
    # The last alarm that triggered, even if no alarm is active now. See
    # ALARM_CODES.
    "BA91": _Known(key="alarm_code"),
    # Operating hours and calculated power
    "6C55": _Known(key="compressor_hours_heating"),
    "6C56": _Known(key="compressor_hours_hot_water"),
    "6C58": _Known(key="aux_heater_hours_heating"),
    "6C59": _Known(key="aux_heater_hours_hot_water"),
    "CFAA": _Known(key="power_consumption"),
    "5FAB": _Known(key="accumulated_consumption"),
    # Settings
    "0203": _Known(key="room_setpoint", minimum=5, maximum=29, step=0.1),
    # The H66 web page shows the raw value unscaled (5 -> "5.0"), unlike the
    # other 2xxx variables.
    "2204": _Known(key="room_sensor_influence", scale=1),
    "2205": _Known(key="heat_curve", minimum=0, maximum=10, step=0.1),
    "0207": _Known(key="heat_curve_parallel", minimum=-10, maximum=10, step=0.1),
    "0208": _Known(key="hot_water_stop_temperature", minimum=20, maximum=60, step=0.1),
    "020B": _Known(key="hot_water_difference", minimum=2, maximum=15, step=0.1),
    "7209": _Known(key="extra_hot_water", minimum=0, maximum=1440, step=1),
    # Takes effect the next time the electric heater would start.
    "1215": _Known(key="electric_heater_allowed", minimum=0, maximum=1, step=1),
    # 1 allows 3 kW, 2 allows 6 kW, 4 allows 9 kW.
    "B21B": _Known(
        key="electric_heater_max_power", minimum=1, maximum=4, options=(1, 2, 4)
    ),
    # Write-only; Husdata warns it can behave unpredictably on a Rego 600.
    "1233": _Known(
        key="external_control", minimum=0, maximum=1, step=1, write_only=True
    ),
    "020A": _Known(key="summer_mode", minimum=0, maximum=30, step=0.1),
    # Days. While it is active, set it to 0 before setting a new value. The
    # register holds whole days, not tenths like other 2xxx variables: writing
    # raw 10 showed "10.0" on the H66 web page (verified on a Rego 600).
    "2210": _Known(
        key="holiday_mode", unit="d", scale=1, minimum=0, maximum=30, step=1
    ),
    # Writing 0 resets an alarm: the heat pump turns off for 10 s and back on.
    "12F2": _Known(key="alarm_reset", minimum=0, maximum=1, step=1),
}

ALARM_CODES: dict[int, str] = {
    1: "Sensor radiator return (GT1)",
    2: "Outdoor sensor (GT2)",
    3: "Sensor hot water (GT3)",
    4: "Mixing valve sensor (GT4)",
    5: "Room sensor (GT5)",
    6: "Sensor compressor (GT6)",
    7: "Sensor heat fluid out (GT8)",
    8: "Sensor heat fluid in (GT9)",
    9: "Sensor cold fluid in (GT10)",
    # Husdata's list says "in", but GT11 is the brine out sensor (see 19).
    10: "Sensor cold fluid out (GT11)",
    11: "Compressor circuit switch",
    12: "Electrical cassette",
    13: "Pump circuit switch (MB2)",
    14: "Low pressure switch (LP)",
    15: "High pressure switch (HP)",
    16: "High return HP (GT9)",
    17: "Heat carrier out max (GT8)",
    18: "Brine in under limit (GT10)",
    19: "Brine out under limit (GT11)",
    20: "Compressor superheat (GT6)",
    21: "3-phase incorrect order",
    22: "Power failure",
    23: "Heat delta exceeded",
}
"""Rego 600/637 alarm codes as reported in ``alarm_code`` (BA91), from Husdata."""


def alarm_text(code: int | None) -> str | None:
    """Return the description of a Rego alarm code, or ``None`` if unknown."""
    return None if code is None else ALARM_CODES.get(code)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "register"


def make_register(
    variable_id: str, address: int, name: str, *, writable: bool
) -> Register:
    """Build a ``Register`` for a variable, using what is known about its ID.

    Unknown IDs (for example custom registers) get a key derived from the ID
    and the name, and the default scaling for their kind.
    """
    variable_id = variable_id.upper()
    kind = kind_from_variable_id(variable_id)
    scale, unit = _KIND_DEFAULTS[kind]
    known = KNOWN_VARIABLES.get(variable_id)
    if known is None:
        return Register(
            key=f"var_{variable_id.lower()}_{_slug(name)}",
            variable_id=variable_id,
            address=address,
            name=name,
            writable=writable,
            kind=kind,
            scale=scale,
            unit=unit,
        )
    return Register(
        key=known.key,
        variable_id=variable_id,
        address=address,
        name=name,
        writable=writable,
        kind=kind,
        scale=known.scale if known.scale is not None else scale,
        unit=known.unit if known.unit is not None else unit,
        minimum=known.minimum,
        maximum=known.maximum,
        step=known.step,
        options=known.options,
        write_only=known.write_only,
    )


# (variable ID, H66 name, writable), in Modbus address order, as served by an
# H66 on firmware 360801 connected to a Rego 600 controller (IVT Greenline).
_REGO600_TABLE: tuple[tuple[str, str, bool], ...] = (
    ("0001", "Radiator Return", False),
    ("0002", "Radiator Forward", False),
    ("0003", "Heat carrier Return", False),
    ("0004", "Heat carrier Forwrd", False),
    ("0005", "Brine in/Evaporator", False),
    ("0006", "Brine out/Condenser", False),
    ("0007", "Outdoor", False),
    ("0008", "Indoor", False),
    ("0009", "Warm water 1 / Top", False),
    ("000A", "Warm water 2 / Mid", False),
    ("000B", "Hot gas", False),
    ("3104", "Add heat status", False),
    ("0107", "Heating setpoint", False),
    ("0111", "Warm water setpoint", False),
    ("0203", "Room temp setpoint", True),
    ("2204", "Room sensor influence", True),
    ("2205", "Heat set 1, CurveL", True),
    ("0207", "Heat set 3, Parallel", True),
    ("0208", "Warm Water stop temp", True),
    ("020B", "Warm water Difference", True),
    ("7209", "Extra Warm Water", True),
    ("1215", "Elect. heater switch", True),
    ("B21B", "Elect. heater Max powr", True),
    ("1233", "External control", True),
    ("020A", "Summer mode", True),
    ("2210", "Holiday mode", True),
    ("12F2", "Alarm reset", True),
    ("1A01", "Compressor", False),
    ("1A02", "Add heat step 1", False),
    ("1A03", "Add heat step 2", False),
    ("1A04", "Pump Cold circuit", False),
    ("1A05", "Pump Heat circuit", False),
    ("1A06", "Pump Radiator", False),
    ("1A07", "Switch valve 1", False),
    ("1A20", "Alarm", False),
    ("BA91", "Alarm Code", False),
    ("6C55", "Compr. cons. heating", False),
    ("6C56", "Compr. cons. hotwat", False),
    ("6C58", "Aux cons. heating", False),
    ("6C59", "Aux cons. hot water", False),
    ("CFAA", "Power consumption", False),
    ("5FAB", "Accumulated consumption", False),
)

REGO600_REGISTERS: tuple[Register, ...] = tuple(
    make_register(variable_id, address, name, writable=writable)
    for address, (variable_id, name, writable) in enumerate(_REGO600_TABLE)
)
"""Default register map: H66 firmware 360801 with a Rego 600 controller."""
