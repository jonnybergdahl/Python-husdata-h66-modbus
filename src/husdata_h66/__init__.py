"""Async Modbus TCP library for the Husdata H66 heat pump gateway."""

from .device import HusdataH66
from .registers import (
    KNOWN_VARIABLES,
    MAX_REGISTERS_PER_REQUEST,
    NO_SENSOR,
    REGO600_REGISTERS,
    Register,
    VariableKind,
    kind_from_variable_id,
    make_register,
)
from .web import parse_controller, parse_firmware_version, parse_registers

__all__ = [
    "KNOWN_VARIABLES",
    "MAX_REGISTERS_PER_REQUEST",
    "NO_SENSOR",
    "REGO600_REGISTERS",
    "HusdataH66",
    "Register",
    "VariableKind",
    "kind_from_variable_id",
    "make_register",
    "parse_controller",
    "parse_firmware_version",
    "parse_registers",
]
