"""Tests for the register map and the web page parser."""

from __future__ import annotations

import pytest

from husdata_h66 import (
    REGO600_REGISTERS,
    VariableKind,
    kind_from_variable_id,
    parse_controller,
    parse_firmware_version,
    parse_registers,
)


@pytest.mark.parametrize(
    ("variable_id", "kind"),
    [
        ("0007", VariableKind.TEMPERATURE),
        ("1A01", VariableKind.STATUS),
        ("2205", VariableKind.NUMBER),
        ("3104", VariableKind.PERCENT),
        ("5FAB", VariableKind.ENERGY),
        ("6C55", VariableKind.HOURS),
        ("7209", VariableKind.MINUTES),
        ("b21b", VariableKind.INTEGER),
        ("CFAA", VariableKind.POWER),
        ("9ABC", VariableKind.OTHER),
    ],
)
def test_kind_from_variable_id(variable_id: str, kind: VariableKind) -> None:
    assert kind_from_variable_id(variable_id) is kind


def test_default_map_is_sequential_and_unique() -> None:
    assert [r.address for r in REGO600_REGISTERS] == list(range(42))
    assert len({r.key for r in REGO600_REGISTERS}) == 42
    assert len({r.variable_id for r in REGO600_REGISTERS}) == 42


def test_parse_registers_matches_default_map(home_page: str) -> None:
    assert tuple(parse_registers(home_page)) == REGO600_REGISTERS


def test_parse_status(home_page: str) -> None:
    assert parse_firmware_version(home_page) == "360801"
    assert parse_controller(home_page) == "Rego 600"


def test_parse_registers_handles_moved_and_custom_registers() -> None:
    page = (
        "<table><tr><td>Idx</td><td>Modbus</td><td>Name</td><td>Value</td></tr>"
        "<tr><td>&nbsp;0007</td><td>3&nbsp;Input</td><td>Outdoor</td>"
        "<td>3.6&nbsp;C</td></tr>"
        "<tr><td>&nbsp;1A01</td><td>4&nbsp;Input</td><td>Compressor  2150W</td>"
        "<td>1</td></tr>"
        "<tr><td>&nbsp;0203</td><td>5&nbsp;Hold</td><td>Room temp setpoint</td>"
        "<td>21.0&nbsp;C</td></tr>"
        "<tr><td>&nbsp;2abc</td><td>6&nbsp;Hold</td><td>My Setting</td>"
        "<td>1.0</td></tr></table>"
    )
    registers = {r.key: r for r in parse_registers(page)}

    assert registers["outdoor"].address == 3
    assert registers["compressor"].name == "Compressor"
    assert registers["room_setpoint"].writable
    custom = registers["var_2abc_my_setting"]
    assert custom.variable_id == "2ABC"
    assert custom.address == 6
    assert custom.writable
    assert custom.scale == 0.1


def test_parse_registers_without_table() -> None:
    with pytest.raises(ValueError):
        parse_registers("<html><body>Login</body></html>")
