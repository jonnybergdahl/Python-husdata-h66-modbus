"""Shared fixtures: register values captured from a real H66 (Rego 600)."""

from __future__ import annotations

from pathlib import Path

import pytest
from modbus_connection.mock import MockModbusUnit

FIXTURES = Path(__file__).parent / "fixtures"

# Raw registers read from an H66 on firmware 360801 with a Rego 600. The H66
# answers the same table on both register spaces.
CAPTURED = [
    395, 65053, 405, 471, 60, 14, 35, 65053, 531, 65053, 729, 0, 392, 510,
    210, 5, 65, 15, 510, 40, 0, 1, 2, 0, 180, 0, 1,
    1, 0, 0, 1, 1, 1, 0, 0, 19, 37018, 10760, 565, 78, 2150, 2,
]  # fmt: skip


@pytest.fixture
def home_page() -> str:
    """The H66 home page (IP and MAC address replaced)."""
    return (FIXTURES / "h66_home.html").read_text()


@pytest.fixture
def unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    """A mock unit loaded with the captured registers."""
    table = dict(enumerate(CAPTURED))
    mock_modbus_unit.load_raw({"input": table, "holding": table})
    return mock_modbus_unit
