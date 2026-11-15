"""The Husdata H66 device, built on a ``modbus_connection`` unit."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from modbus_connection.model import (
    Device,
    ManualComponent,
    UpdateReport,
    boolean,
    gauge,
    integer,
)

from .registers import (
    MAX_REGISTERS_PER_REQUEST,
    NO_SENSOR,
    REGO600_REGISTERS,
    Register,
    VariableKind,
)

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit
    from modbus_connection.model import Range, RegisterField


def _validator(register: Register) -> Any:
    """Return a write validator that enforces the register's range and step."""

    def validate(value: Any) -> Any:
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, int | float) or math.isnan(value):
            raise ValueError(f"{register.key}: {value!r} is not a number")
        if register.minimum is not None and value < register.minimum:
            raise ValueError(f"{register.key}: {value} is below {register.minimum}")
        if register.maximum is not None and value > register.maximum:
            raise ValueError(f"{register.key}: {value} is above {register.maximum}")
        if register.step:
            base = register.minimum or 0
            steps = (value - base) / register.step
            if abs(steps - round(steps)) > 1e-6:
                raise ValueError(
                    f"{register.key}: {value} is not a multiple of {register.step}"
                )
        return value

    return validate


def _field(register: Register) -> RegisterField[Any]:
    writable = _validator(register) if register.writable else False
    if register.kind is VariableKind.STATUS:
        return boolean(register.address, writable=writable)
    nan = NO_SENSOR if register.kind is VariableKind.TEMPERATURE else None
    if register.scale == 1:
        return integer(
            register.address,
            signed=register.signed,
            nan=nan,
            writable=writable,
            unit=register.unit,
        )
    return gauge(
        register.address,
        register.scale,
        signed=register.signed,
        nan=nan,
        writable=writable,
        unit=register.unit,
    )


def _ranges(addresses: Iterable[int]) -> tuple[Range, ...]:
    """Group addresses into contiguous inclusive ranges."""
    ranges: list[list[int]] = []
    for address in sorted(set(addresses)):
        if ranges and address == ranges[-1][1] + 1:
            ranges[-1][1] = address
        else:
            ranges.append([address, address])
    return tuple((low, high) for low, high in ranges)


class HusdataH66(Device):
    """A heat pump read and controlled through a Husdata H66 gateway.

    The device never opens a connection itself: pass it a ``ModbusUnit`` from
    ``modbus_connection`` (or from Home Assistant's ``async_get_unit``).

    Values are keyed by ``Register.key``, for example ``"outdoor"`` or
    ``"room_setpoint"``. Temperatures are in °C, a disconnected sensor reads
    ``None``, status variables are ``bool``.
    """

    def __init__(
        self,
        unit: ModbusUnit,
        registers: Iterable[Register] = REGO600_REGISTERS,
    ) -> None:
        super().__init__(unit)
        self.registers: dict[str, Register] = {}
        addresses: dict[str, set[int]] = {"input": set(), "holding": set()}
        for register in registers:
            if register.key in self.registers:
                raise ValueError(f"duplicate register key {register.key!r}")
            self.registers[register.key] = register
            addresses[register.space].add(register.address)
        self.heat_pump = ManualComponent(
            unit,
            max_span=MAX_REGISTERS_PER_REQUEST,
            input_ranges=_ranges(addresses["input"]),
            holding_ranges=_ranges(addresses["holding"]),
        )
        for register in self.registers.values():
            self.heat_pump.add(register.key, _field(register), space=register.space)

    async def async_update(self) -> UpdateReport:
        """Read all registers.

        Raises ``ModbusConnectionError`` or ``ModbusTimeoutError`` when the
        gateway cannot be reached; other Modbus errors land in the report.
        """
        return await self.async_poll(("heat_pump",))

    @property
    def values(self) -> dict[str, Any]:
        """All values from the last update, keyed by register key."""
        return self.heat_pump.values

    def get(self, key: str) -> Any:
        """Return one value from the last update (``None`` if not read yet)."""
        if key not in self.registers:
            raise KeyError(key)
        return self.heat_pump.get(key)

    def register_by_variable_id(self, variable_id: str) -> Register:
        """Look up a register by its Husdata variable ID, e.g. ``"0203"``."""
        variable_id = variable_id.upper()
        for register in self.registers.values():
            if register.variable_id == variable_id:
                return register
        raise KeyError(variable_id)

    async def async_set(self, key: str, value: float | bool) -> None:
        """Write a setting, in its own unit (e.g. °C for ``room_setpoint``).

        Raises ``KeyError`` for an unknown key, ``AttributeError`` for a
        read-only register and ``ValueError`` for a value outside the
        register's range or step. The new value shows up on the next update.
        """
        if key not in self.registers:
            raise KeyError(key)
        await self.heat_pump.write(key, value)

    async def async_reset_alarm(self) -> None:
        """Reset an active heat pump alarm."""
        await self.async_set("alarm_reset", 1)
