"""Tests for Zebra printer support."""

from collections import deque

import pylabelprinter
from pylabelprinter.enums import PaperType, PrintTechnology
from pylabelprinter.printers.zebra.base import (
    ZebraPrinter,
    _mask_row_padding_bits,
    _normalize_sgd_value,
)


class MockConnection:
    """Mock connection for Zebra tests."""

    def __init__(self, reads=None):
        self.reads = deque(reads or [])
        self.written = []
        self._open = False

    def open(self):
        self._open = True

    def close(self):
        self._open = False

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def read(self, size: int, timeout: float = 1.0) -> bytes:
        if self.reads:
            return self.reads.popleft()
        return b""

    def flush_input(self) -> None:
        return None

    @property
    def is_open(self) -> bool:
        return self._open


class DummyZebraPrinter(ZebraPrinter):
    _MODEL = "Dummy Zebra"
    _MAX_WIDTH_MM = 100
    _MAX_WIDTH_DOTS = 800
    _SUPPORTED_PRINT_TECHNOLOGIES = [
        PrintTechnology.DIRECT_THERMAL,
        PrintTechnology.THERMAL_TRANSFER,
    ]


def test_normalize_sgd_value_strips_quotes():
    assert _normalize_sgd_value('"V89.21.43Z"\r\n') == "V89.21.43Z"


def test_sgd_query_collects_fragmented_response():
    conn = MockConnection([b'"D5J2', b'55114503"\r\n'])
    printer = DummyZebraPrinter(conn)

    assert printer._sgd_query("device.unique_id") == "D5J255114503"


def test_has_paper_false_when_host_status_missing():
    conn = MockConnection([b"", b""])
    printer = DummyZebraPrinter(conn)

    assert printer.has_paper is False


def test_has_paper_reads_host_status_flag():
    conn = MockConnection([b"\x02030,0,0,0284,000,0,0,0,000,0,0,0\x03\r\n"])
    printer = DummyZebraPrinter(conn)

    assert printer.has_paper is True


def test_paper_type_auto_detect_mapping():
    conn = MockConnection([b'"auto_detect"\r\n'])
    printer = DummyZebraPrinter(conn)

    assert printer.paper_type == PaperType.AUTO_DETECT


def test_get_print_technology_maps_transfer():
    conn = MockConnection([b'"thermal trans"\r\n'])
    printer = DummyZebraPrinter(conn)

    assert printer.print_technology == PrintTechnology.THERMAL_TRANSFER


def test_set_print_technology_writes_sgd_command():
    conn = MockConnection()
    printer = DummyZebraPrinter(conn)

    printer.print_technology = PrintTechnology.THERMAL_TRANSFER

    assert conn.written[-1] == b'! U1 setvar "ezpl.print_method" "thermal trans"\r\n'


def test_zd220_default_print_technology_is_transfer():
    printer = pylabelprinter.printers.zebra.ZebraZD220(MockConnection())

    assert printer._PRINT_TECHNOLOGY == PrintTechnology.THERMAL_TRANSFER


def test_mask_row_padding_bits_clears_unused_right_edge_bits():
    masked = _mask_row_padding_bits(
        image_bytes=bytes([0xFF, 0xFF]),
        width_bytes=1,
        width_dots=5,
        height=2,
    )

    # Bei 5 Nutzbits müssen die 3 rechten Padding-Bits gelöscht werden.
    assert masked == bytes([0xF8, 0xF8])