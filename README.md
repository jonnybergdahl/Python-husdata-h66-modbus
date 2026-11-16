# husdata-h66-modbus

Async Python library for the Modbus TCP interface of the [Husdata H66](https://husdata.se/produkt/h66-wifi-eth-gateway-styr-din-varmepump/) heat pump gateway.

It is built on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection), the Modbus layer Home Assistant uses from 2026.9. The library never opens a connection itself: you give it a `ModbusUnit`, either from `modbus_connection` or from Home Assistant's `async_get_unit`. It has no Home Assistant dependency.

Tested with an H66 on firmware 360801 connected to an IVT Greenline (Rego 600 controller).

## Installation

```bash
pip install husdata-h66-modbus
```

Add the `cli` extra to get the pymodbus backend and the `husdata-h66` command line tool:

```bash
pip install "husdata-h66-modbus[cli]"
```

## Documentation

The full library documentation can be [found here](https://jonnybergdahl.github.io/husdata-h66-modbus/).

## Enable Modbus on the H66

Modbus TCP is off by default. On the H66 web page, open **Config** > **Modbus**, set `MODBUS_PORT` to `502` and restart the H66. `MODBUS_IP` can limit which client may connect. The H66 accepts only one Modbus client at a time.

## Usage

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from husdata_h66 import HusdataH66


async def main() -> None:
    connection = ModbusConnection(ModbusTcpParams(host="h66.local"))
    try:
        device = HusdataH66(connection.for_unit(1))
        await device.async_update()
        print(device.get("outdoor"))  # 3.5 (°C)
        print(device.get("compressor"))  # True
        print(device.values)  # everything, keyed by register key

        await device.async_set("room_setpoint", 21.5)
    finally:
        await connection.close()


asyncio.run(main())
```

In Home Assistant, pass the unit from `async_get_unit` instead:

```python
unit = async_get_unit(
    hass, entry, ModbusTcpParams(host=entry.data[CONF_HOST]), entry.data[CONF_UNIT_ID]
)
entry.runtime_data = HusdataH66(unit)
```

`async_update()` reads all registers in three requests and returns an `UpdateReport`. It raises `ModbusConnectionError` or `ModbusTimeoutError` when the gateway cannot be reached.

`async_set()` takes the value in the register's own unit and checks it against the register's range and step. It raises `ValueError` for an invalid value and `AttributeError` for a read-only register. `async_reset_alarm()` writes 0 to **Alarm reset**, which turns the heat pump off for 10 seconds and then on again.

From the command line (read-only):

```bash
husdata-h66 h66.local
```

## Register map

The H66 numbers its Modbus registers one per parameter, in the order its home page lists them. Read-only parameters are INPUT registers, settings are HOLDING registers, and every register is a signed or unsigned 16-bit value. The addresses depend on the heat pump controller and can move after a firmware update or when you add custom registers in the H66.

`REGO600_REGISTERS` is the default map, for a Rego 600 controller on firmware 360801. To follow the H66 instead, fetch its home page and parse it:

```python
from husdata_h66 import HusdataH66, parse_firmware_version, parse_registers

page = await (await session.get("http://h66.local/")).text()
device = HusdataH66(unit, parse_registers(page))
```

`husdata-h66 h66.local --from-web` does the same from the command line.

Each parameter has a Husdata variable ID. Its first hex digit gives the type and scaling:

| First digit | Type | Scale | Unit |
|---|---|---|---|
| 0 | Temperature | 0.1 | °C |
| 1 | Status | 1 | on/off |
| 2 | Number | 0.1 | |
| 3 | Percent | 0.1 | % |
| 5 | Energy | 0.1 | kWh |
| 6 | Hours | 1 | h |
| 7 | Minutes | 1 | min |
| B | Integer | 1 | |
| C | Power | 1 | W |

Temperatures and numbers are signed, the others unsigned. A temperature sensor that isn't connected reads `None` (the H66 shows −48.3 °C).

### Rego 600 (default map)

| Address | Type | ID | Key | Range |
|---|---|---|---|---|
| 0 | Input | 0001 | `radiator_return` | |
| 1 | Input | 0002 | `radiator_forward` | |
| 2 | Input | 0003 | `heat_carrier_return` | |
| 3 | Input | 0004 | `heat_carrier_forward` | |
| 4 | Input | 0005 | `brine_in` | |
| 5 | Input | 0006 | `brine_out` | |
| 6 | Input | 0007 | `outdoor` | |
| 7 | Input | 0008 | `indoor` | |
| 8 | Input | 0009 | `hot_water_top` | |
| 9 | Input | 000A | `hot_water_mid` | |
| 10 | Input | 000B | `hot_gas` | |
| 11 | Input | 3104 | `add_heat_status` | |
| 12 | Input | 0107 | `heating_setpoint` | |
| 13 | Input | 0111 | `hot_water_setpoint` | |
| 14 | Holding | 0203 | `room_setpoint` | 5–29 °C |
| 15 | Holding | 2204 | `room_sensor_influence` | |
| 16 | Holding | 2205 | `heat_curve` | 0–10 |
| 17 | Holding | 0207 | `heat_curve_parallel` | −10–10 °C |
| 18 | Holding | 0208 | `hot_water_stop_temperature` | 20–60 °C |
| 19 | Holding | 020B | `hot_water_difference` | 2–15 °C |
| 20 | Holding | 7209 | `extra_hot_water` | 0–1440 min |
| 21 | Holding | 1215 | `electric_heater_allowed` | on/off |
| 22 | Holding | B21B | `electric_heater_max_power` | 1 (3 kW), 2 (6 kW) or 4 (9 kW) |
| 23 | Holding | 1233 | `external_control` | on/off, write-only |
| 24 | Holding | 020A | `summer_mode` | 0–30 °C |
| 25 | Holding | 2210 | `holiday_mode` | 0–30 days |
| 26 | Holding | 12F2 | `alarm_reset` | write 0 to reset |
| 27 | Input | 1A01 | `compressor` | |
| 28 | Input | 1A02 | `add_heat_step_1` | |
| 29 | Input | 1A03 | `add_heat_step_2` | |
| 30 | Input | 1A04 | `pump_cold_circuit` | |
| 31 | Input | 1A05 | `pump_heat_circuit` | |
| 32 | Input | 1A06 | `pump_radiator` | |
| 33 | Input | 1A07 | `switch_valve_1` | off: heating, on: hot water |
| 34 | Input | 1A20 | `alarm` | |
| 35 | Input | BA91 | `alarm_code` | last alarm, see below |
| 36 | Input | 6C55 | `compressor_hours_heating` | |
| 37 | Input | 6C56 | `compressor_hours_hot_water` | |
| 38 | Input | 6C58 | `aux_heater_hours_heating` | |
| 39 | Input | 6C59 | `aux_heater_hours_hot_water` | |
| 40 | Input | CFAA | `power_consumption` | |
| 41 | Input | 5FAB | `accumulated_consumption` | |

`power_consumption` and `accumulated_consumption` are calculated by the H66 from the wattages set for each status variable on its web page. `accumulated_consumption` restarts at 0 when the H66 boots.

The meanings and ranges come from Husdata's [variable list for Rego 600/637](https://online.husdata.se/h-docs/C00.pdf). Some details from it:

- `alarm_code` is the last alarm that triggered, even if no alarm is active now. `alarm_text(code)` and `ALARM_CODES` give its description.
- `external_control` is write-only: the value read back means nothing. Husdata warns it can behave unpredictably on a Rego 600.
- `electric_heater_allowed` takes effect the next time the electric heater would start.
- `holiday_mode` is in whole days, stored unscaled (unlike the other 2xxx numbers, which are ×10). While it is active, set it to 0 before setting a new value.
- `extra_hot_water`: on a Rego 600, a value written over Modbus shows on the H66 web page for about 20 seconds and is then reset to 0, and no hot water production starts. How to set it is still unknown.

Not yet verified: `room_sensor_influence` is read unscaled because the H66 web page shows it that way.

### Alarm codes

| Code | Alarm |
|---|---|
| 1 | Sensor radiator return (GT1) |
| 2 | Outdoor sensor (GT2) |
| 3 | Sensor hot water (GT3) |
| 4 | Mixing valve sensor (GT4) |
| 5 | Room sensor (GT5) |
| 6 | Sensor compressor (GT6) |
| 7 | Sensor heat fluid out (GT8) |
| 8 | Sensor heat fluid in (GT9) |
| 9 | Sensor cold fluid in (GT10) |
| 10 | Sensor cold fluid out (GT11) |
| 11 | Compressor circuit switch |
| 12 | Electrical cassette |
| 13 | Pump circuit switch (MB2) |
| 14 | Low pressure switch (LP) |
| 15 | High pressure switch (HP) |
| 16 | High return HP (GT9) |
| 17 | Heat carrier out max (GT8) |
| 18 | Brine in under limit (GT10) |
| 19 | Brine out under limit (GT11) |
| 20 | Compressor superheat (GT6) |
| 21 | 3-phase incorrect order |
| 22 | Power failure |
| 23 | Heat delta exceeded |

## Development

```bash
uv sync
uv run pytest
uv run ruff check src tests
```

`build.sh` publishes a release: it converts this README to `README.rst`, builds the documentation, copies it to the `jonnybergdahl.github.io` repository and pushes it, then builds the package and uploads it to PyPI.

## License

MIT
