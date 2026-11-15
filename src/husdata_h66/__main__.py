"""Command line tool: read and print all values from an H66 (read-only)."""

from __future__ import annotations

import argparse
import asyncio
import urllib.request

from modbus_connection import ModbusTcpParams

from .device import HusdataH66
from .registers import REGO600_REGISTERS, Register
from .web import parse_firmware_version, parse_registers


def _fetch_registers(host: str) -> tuple[list[Register], str | None]:
    with urllib.request.urlopen(f"http://{host}/", timeout=10) as response:
        page = response.read().decode("utf-8", errors="replace")
    return parse_registers(page), parse_firmware_version(page)


def _format(register: Register, value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "on" if value else "off"
    unit = f" {register.unit}" if register.unit else ""
    return f"{value}{unit}"


async def _run(args: argparse.Namespace) -> None:
    try:
        from modbus_connection.pymodbus import ModbusConnection
    except ImportError as err:  # pragma: no cover
        raise SystemExit("install with the 'cli' extra to use this tool") from err

    registers: list[Register] | tuple[Register, ...] = REGO600_REGISTERS
    if args.from_web:
        registers, version = await asyncio.to_thread(_fetch_registers, args.host)
        print(f"Register map from web page (firmware {version})")

    connection = ModbusConnection(ModbusTcpParams(host=args.host, port=args.port))
    try:
        device = HusdataH66(connection.for_unit(args.unit_id), registers)
        report = await device.async_update()
        for name, err in report.failed.items():
            print(f"Read of {name} failed: {err}")
        for register in device.registers.values():
            print(
                f"{register.address:>3} {register.space:<7} {register.variable_id} "
                f"{register.key:<28} {_format(register, device.get(register.key))}"
            )
    finally:
        await connection.close()


def main() -> None:
    """Entry point for ``husdata-h66``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="H66 host name or IP address")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument(
        "--from-web",
        action="store_true",
        help="read the register map from the H66 web page instead of the default",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
