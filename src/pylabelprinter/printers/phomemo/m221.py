"""
Phomemo M221 Label-Drucker Treiber.

Modellspezifisch:
    - Druckbreite: 72mm (576 dots)
    - Bildkompression: miniLZO
    - Drucksequenz: Init → Compress Ein → Kopien → Bild → Compress Aus
"""

import time
from typing import Optional, Union

from ...enums import PrintDensity
from ...registry import register_printer

from .base import PhomemoPrinter, probe_phomemo_usb
from .protocol import PhomemoProtocol, minilzo_compress


@register_printer(
    usb_vid=0x0483,
    usb_pid=0x5740,
    name="Phomemo M221",
    manufacturer="Phomemo",
    model="M221",
    probe=probe_phomemo_usb,
)
class PhomemoM221(PhomemoPrinter):
    """Phomemo M221 USB Label-Drucker.
    
    Spezifikationen:
        - Auflösung: 203 DPI (8 dots/mm)
        - Maximale Druckbreite: 72mm (576 dots)
        - USB: VID 0x0483, PID 0x5740
        - Protokoll: Proprietär mit LZO-Kompression
    """
    
    _MODEL = "M221"
    _MAX_WIDTH_MM = 72
    _MAX_WIDTH_DOTS = 576
    
    def _send_print_sequence(
        self,
        raw_data: bytes,
        width_bytes: int,
        height: int,
        copies: int,
        density: Optional[Union[PrintDensity, int]],
    ) -> None:
        """M221 Drucksequenz: Init → Density → Compress Ein → Kopien → Bild → Compress Aus."""
        # LZO komprimieren
        compressed = minilzo_compress(raw_data)
        
        # Header: width_bytes (2 bytes LE) + height (2 bytes LE)
        header = bytes([
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            height & 0xFF, (height >> 8) & 0xFF,
        ])
        
        # 1. Init
        self._conn.write(PhomemoProtocol.CMD_INIT_PRINTER)
        time.sleep(0.05)
        
        # 2. Density (optional)
        self._send_density(density)
        
        # 3. Enter Compress Mode
        self._conn.write(PhomemoProtocol.CMD_ENTER_COMPRESS)
        time.sleep(0.05)
        
        # 4. Set Copies
        self._conn.write(PhomemoProtocol.CMD_PRINT_MULTI + bytes([copies]))
        time.sleep(0.05)
        
        # 5. Print Image (ein Block mit Header + komprimierte Daten)
        self._conn.write(PhomemoProtocol.CMD_PRINT_IMAGE + header + compressed)
        time.sleep(0.1)
        
        # 6. Exit Compress Mode
        self._conn.write(PhomemoProtocol.CMD_EXIT_COMPRESS)
