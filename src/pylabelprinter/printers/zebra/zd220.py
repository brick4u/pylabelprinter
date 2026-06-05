"""
Zebra ZD220 / ZD220t Label-Drucker Treiber.

Modellspezifisch:
    - Druckbreite: 104mm (832 dots bei 203 DPI)
    - Auflösung: 203 DPI
    - Thermal Transfer (t) oder Direct Thermal
    - USB: VID 0x0a5f, PID 0x0164 (ZTC ZD220-203dpi ZPL)
    - Protokoll: ZPL II text-basiert
"""

from ...registry import register_printer
from .base import ZebraPrinter, probe_zebra_usb
from ...enums import PrintTechnology


@register_printer(
    usb_vid=0x0a5f,
    usb_pid=0x0164,
    name="Zebra ZD220-203dpi ZPL",
    manufacturer="Zebra Technologies",
    model="ZTC ZD220-203dpi ZPL",
    probe=probe_zebra_usb,
)
class ZebraZD220(ZebraPrinter):
    """Zebra ZD220 4-inch Desktop Printer.
    
    Spezifikationen:
        - Auflösung: 203 DPI (8 dots/mm)
        - Maximale Druckbreite: 104mm (832 dots)
        - USB: VID 0x0a5f, PID 0x0164
        - Protokoll: ZPL II (text-basiert)
        - Print Method: Direct Thermal oder Thermal Transfer
    """
    
    _MODEL = "ZTC ZD220-203dpi ZPL"
    _MAX_WIDTH_MM = 104
    _MAX_WIDTH_DOTS = 832
    _PRINT_TECHNOLOGY = PrintTechnology.THERMAL_TRANSFER
    
    # Überschreibe Klassenkonstanten der Basis
    _SUPPORTED_PRINT_TECHNOLOGIES = [PrintTechnology.DIRECT_THERMAL, PrintTechnology.THERMAL_TRANSFER]