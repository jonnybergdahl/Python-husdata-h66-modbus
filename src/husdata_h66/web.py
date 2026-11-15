"""Read the register map from the H66 web page.

The H66 publishes no register list over Modbus, and the addresses can move
after a firmware update or when custom registers are added. Its home page
lists every parameter with its Modbus address and register type, so the
reliable way to get the current map is to parse that page.

This module only parses HTML. Fetching the page is left to the caller, so a
Home Assistant integration can use its own HTTP session.
"""

from __future__ import annotations

import html as html_lib
import re

from .registers import Register, make_register

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_VARIABLE_ID = re.compile(r"^[0-9A-Fa-f]{4}$")
_MODBUS = re.compile(r"^(\d+)\s+(Input|Hold)", re.IGNORECASE)
# Trailing wattage the H66 appends to a name when one is configured,
# e.g. "Compressor  2150W".
_WATTAGE = re.compile(r"\s+\d+\s*W$")
_STATUS_VERSION = re.compile(r"Version\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>", re.I)
_STATUS_CONTROLLER = re.compile(
    r"Controller\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>", re.I
)


def _text(cell: str) -> str:
    text = html_lib.unescape(_TAG.sub("", cell)).replace("\xa0", " ")
    return " ".join(text.split())


def parse_registers(page: str) -> list[Register]:
    """Parse the parameter table of the H66 home page into registers.

    Raises ``ValueError`` if the page has no parameter table.
    """
    registers: list[Register] = []
    for row in _ROW.findall(page):
        cells = [_text(cell) for cell in _CELL.findall(row)]
        if len(cells) < 3 or not _VARIABLE_ID.match(cells[0]):
            continue
        match = _MODBUS.match(cells[1])
        if match is None:
            continue
        name = _WATTAGE.sub("", cells[2]).strip()
        registers.append(
            make_register(
                cells[0],
                int(match.group(1)),
                name,
                writable=match.group(2).lower() == "hold",
            )
        )
    if not registers:
        raise ValueError("no H66 parameter table found in page")
    return registers


def parse_firmware_version(page: str) -> str | None:
    """Return the H66 firmware version from its home page, if present."""
    match = _STATUS_VERSION.search(page)
    return match.group(1) if match else None


def parse_controller(page: str) -> str | None:
    """Return the heat pump controller name from the H66 home page, if present."""
    match = _STATUS_CONTROLLER.search(page)
    return match.group(1) if match else None
