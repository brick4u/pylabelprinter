"""
Phomemo M120 Label-Drucker Treiber.

Modellspezifisch:
    - Druckbreite: 48mm (384 dots)
    - Bildkompression: Keine (unkomprimierte Raw-Bitmap)
    - Drucksequenz: Init → Kopien → Bild
"""

import time
from typing import Optional, Union

from ...enums import Alignment, PrintDensity
from ...registry import register_printer

from .base import PhomemoPrinter, probe_phomemo_usb
from .protocol import PhomemoProtocol


@register_printer(
    usb_vid=0x0483,
    usb_pid=0x5740,
    name="Phomemo M120",
    manufacturer="Phomemo",
    model="M120",
    probe=probe_phomemo_usb,
)
class PhomemoM120(PhomemoPrinter):
    """Phomemo M120 USB Label-Drucker.
    
    Spezifikationen:
        - Auflösung: 203 DPI (8 dots/mm)
        - Maximale Druckbreite: 48mm (384 dots)
        - USB: VID 0x0483, PID 0x5740
        - Protokoll: Proprietär, unkomprimiert
    """
    
    _MODEL = "M120"
    _MAX_WIDTH_MM = 48
    _MAX_WIDTH_DOTS = 384
    _DEFAULT_ALIGNMENT = Alignment.RIGHT
    
    def _send_print_sequence(
        self,
        raw_data: bytes,
        width_bytes: int,
        height: int,
        copies: int,
        density: Optional[Union[PrintDensity, int]],
    ) -> None:
        """M120 Drucksequenz: Init → Density → Kopien → Bild (kein Compress Mode).
        
        Im Gegensatz zum M221 werden die Bilddaten unkomprimiert gesendet,
        als ein einzelner GS v 0 Block mit allen Zeilen.
        Das USB-Chunking in UsbConnection sorgt für Flow Control.
        """
        # Header: GS v 0 + mode(0) + width_bytes (2 LE) + height (2 LE)
        header = PhomemoProtocol.CMD_PRINT_IMAGE + bytes([
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            height & 0xFF, (height >> 8) & 0xFF,
        ])
        
        # 1. Init
        self._conn.write(PhomemoProtocol.CMD_INIT_PRINTER)
        time.sleep(0.05)
        
        # 2. Density (optional)
        self._send_density(density)
        
        # 3. Set Copies
        self._conn.write(PhomemoProtocol.CMD_PRINT_MULTI + bytes([copies]))
        time.sleep(0.05)
        
        # 4. Print Image (ein Block mit Header + alle Pixeldaten)
        self._conn.write(header + raw_data)
        time.sleep(0.1)
