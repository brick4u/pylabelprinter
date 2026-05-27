"""Tests for Phomemo M221 printer."""

import pytest
from pylabelprinter import AutoOffTime
from pylabelprinter.printers import PhomemoM221


class MockConnection:
    """Mock connection for testing."""
    
    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.written = []
        self._open = False
    
    def open(self):
        self._open = True
    
    def close(self):
        self._open = False
    
    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)
    
    def read(self, size: int, timeout_ms: int = 500) -> bytes:
        return b""
    
    def query(self, command: bytes, timeout_ms: int = 500) -> bytes:
        self.write(command)
        # Return mock response based on command
        cmd = command[-1] if command else 0
        return self.responses.get(cmd, b"")
    
    @property
    def is_open(self) -> bool:
        return self._open


class TestPhomemoM221:
    """Test cases for PhomemoM221."""
    
    def test_firmware_version(self):
        """Test firmware version parsing."""
        conn = MockConnection({
            0x07: bytes([0x1A, 0x07, 0x02, 0x00, 0x08])  # Version 2.0.8
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.firmware_version == "2.0.8"
    
    def test_battery_level(self):
        """Test battery level parsing."""
        conn = MockConnection({
            0x08: bytes([0x1A, 0x04, 100])  # 100%
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.battery_level == 100
    
    def test_serial_number(self):
        """Test serial number parsing."""
        conn = MockConnection({
            0x09: bytes([0x1A, 0x08]) + b"Q218G4C48320027"
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.serial_number == "Q218G4C48320027"
    
    def test_has_paper_true(self):
        """Test paper detection - paper present."""
        conn = MockConnection({
            0x11: bytes([0x1A, 0x06, 0x89])  # Bit 0 = 1
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.has_paper is True
    
    def test_has_paper_false(self):
        """Test paper detection - no paper."""
        conn = MockConnection({
            0x11: bytes([0x1A, 0x06, 0x88])  # Bit 0 = 0
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.has_paper is False
    
    def test_auto_off_time(self):
        """Test auto-off timer query."""
        conn = MockConnection({
            0x0E: bytes([0x1A, 0x09, 0x04])  # 1 hour
        })
        printer = PhomemoM221(conn)
        printer.connect()
        
        assert printer.auto_off_time == AutoOffTime.MIN_15
    
    def test_set_auto_off(self):
        """Test setting auto-off timer."""
        conn = MockConnection()
        printer = PhomemoM221(conn)
        printer.connect()
        
        printer.auto_off_time = AutoOffTime.MIN_20
        
        assert bytes([0x1B, 0x4E, 0x07, 0x05]) in conn.written
    
    def test_context_manager(self):
        """Test context manager protocol."""
        conn = MockConnection()
        
        with PhomemoM221(conn) as printer:
            assert conn.is_open
        
        assert not conn.is_open
