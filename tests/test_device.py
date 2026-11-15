"""Tests for HusdataH66."""

from __future__ import annotations

import pytest
from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit, WriteEvent

from husdata_h66 import MAX_REGISTERS_PER_REQUEST, HusdataH66, make_register


async def test_update_decodes_values(unit: MockModbusUnit) -> None:
    device = HusdataH66(unit)
    report = await device.async_update()

    assert report.complete
    assert device.get("radiator_return") == 39.5
    assert device.get("outdoor") == 3.5
    assert device.get("hot_gas") == 72.9
    assert device.get("add_heat_status") == 0.0
    assert device.get("room_setpoint") == 21.0
    assert device.get("room_sensor_influence") == 5
    assert device.get("heat_curve") == 6.5
    assert device.get("heat_curve_parallel") == 1.5
    assert device.get("extra_hot_water") == 0
    assert device.get("electric_heater_allowed") is True
    assert device.get("electric_heater_max_power") == 2
    assert device.get("external_control") is False
    assert device.get("summer_mode") == 18.0
    assert device.get("compressor") is True
    assert device.get("add_heat_step_1") is False
    assert device.get("alarm") is False
    assert device.get("alarm_code") == 19
    assert device.get("power_consumption") == 2150
    assert device.get("accumulated_consumption") == 0.2


async def test_missing_sensor_is_none(unit: MockModbusUnit) -> None:
    device = HusdataH66(unit)
    await device.async_update()

    assert device.get("radiator_forward") is None
    assert device.get("indoor") is None
    assert device.get("hot_water_mid") is None


async def test_large_counters_are_unsigned(unit: MockModbusUnit) -> None:
    device = HusdataH66(unit)
    await device.async_update()

    assert device.get("compressor_hours_heating") == 37018


async def test_negative_values_are_signed(unit: MockModbusUnit) -> None:
    unit.input[6] = 0x10000 - 125  # outdoor -12.5 °C
    unit.holding[17] = 0x10000 - 20  # parallel offset -2.0
    device = HusdataH66(unit)
    await device.async_update()

    assert device.get("outdoor") == -12.5
    assert device.get("heat_curve_parallel") == -2.0


async def test_reads_follow_h66_limits(unit: MockModbusUnit) -> None:
    device = HusdataH66(unit)
    await device.async_update()

    blocks = [(e.register_type, e.address, e.count) for e in unit.read_events]
    assert sorted(blocks) == [("holding", 14, 13), ("input", 0, 14), ("input", 27, 15)]
    assert all(count <= MAX_REGISTERS_PER_REQUEST for _, _, count in blocks)


async def test_set_writes_scaled_value(unit: MockModbusUnit) -> None:
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)
    device = HusdataH66(unit)

    await device.async_set("room_setpoint", 21.5)
    await device.async_set("heat_curve_parallel", -1.5)
    await device.async_set("extra_hot_water", 120)
    await device.async_set("electric_heater_allowed", False)

    assert [(w.address, w.values) for w in writes] == [
        (14, [215]),
        (17, [0x10000 - 15]),
        (20, [120]),
        (21, [0]),
    ]
    assert all(w.register_type == "holding" for w in writes)


async def test_reset_alarm_writes_zero(unit: MockModbusUnit) -> None:
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    await HusdataH66(unit).async_reset_alarm()

    assert [(w.address, w.values) for w in writes] == [(26, [0])]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("room_setpoint", 4.9),
        ("room_setpoint", 29.5),
        ("room_setpoint", 21.05),
        ("electric_heater_max_power", 3),
        ("electric_heater_max_power", 5),
        ("electric_heater_max_power", 1.5),
        ("heat_curve", float("nan")),
        ("heat_curve", "6"),
    ],
)
async def test_set_rejects_invalid_values(
    unit: MockModbusUnit, key: str, value: object
) -> None:
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    with pytest.raises(ValueError):
        await HusdataH66(unit).async_set(key, value)  # type: ignore[arg-type]
    assert not writes


async def test_set_rejects_read_only_and_unknown(unit: MockModbusUnit) -> None:
    device = HusdataH66(unit)

    with pytest.raises(AttributeError):
        await device.async_set("outdoor", 10)
    with pytest.raises(KeyError):
        await device.async_set("no_such_register", 1)


async def test_connection_error_propagates(unit: MockModbusUnit) -> None:
    unit.fail_requests(ModbusConnectionError("down"))

    with pytest.raises(ModbusConnectionError):
        await HusdataH66(unit).async_update()


async def test_custom_register_map(unit: MockModbusUnit) -> None:
    unit.input[50] = 1234
    registers = [
        make_register("0007", 6, "Outdoor", writable=False),
        make_register("0099", 50, "My sensor", writable=False),
    ]
    device = HusdataH66(unit, registers)
    await device.async_update()

    assert device.values == {"outdoor": 3.5, "var_0099_my_sensor": 123.4}
    assert device.register_by_variable_id("0099").key == "var_0099_my_sensor"


def test_duplicate_keys_rejected(unit: MockModbusUnit) -> None:
    register = make_register("0007", 6, "Outdoor", writable=False)
    with pytest.raises(ValueError, match="duplicate"):
        HusdataH66(unit, [register, register])


@pytest.mark.parametrize("value", [1, 2, 4])
async def test_electric_heater_max_power_accepts_its_steps(
    unit: MockModbusUnit, value: int
) -> None:
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    await HusdataH66(unit).async_set("electric_heater_max_power", value)

    assert [(w.address, w.values) for w in writes] == [(22, [value])]
