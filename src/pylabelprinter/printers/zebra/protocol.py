"""
Zebra-ZPL-Protokoll: ZPL-Befehle, SGD-Mappings und Hilfsfunktionen.
"""

from typing import Dict, Optional

from ...enums import PaperType, Alignment, PrintDensity


class ZPL:
    """ZPL-Befehlskonstanten und Builder.
    
    Referenz: ZPL II Programming Guide (P1134473-08EN Rev A)
    """
    
    # === Rahmenbefehle ===
    CMD_START = b"^XA"         # Format-Start
    CMD_END = b"^XZ"           # Format-Ende
    
    # === Druckparameter ===
    @staticmethod
    def pw(width_dots: int) -> bytes:
        """^PW — Label-Breite in Dots setzen."""
        return f"^PW{width_dots}".encode()
    
    @staticmethod
    def ll(height_dots: int) -> bytes:
        """^LL — Label-Länge in Dots setzen."""
        return f"^LL{height_dots}".encode()
    
    @staticmethod
    def ls(label_length: int) -> bytes:
        """^LS — Label Länge/Abstand."""
        return f"^LS{label_length}".encode()
    
    @staticmethod
    def fo(x: int, y: int) -> bytes:
        """^FO — Feldposition (x,y) in Dots."""
        return f"^FO{x},{y}".encode()
    
    @staticmethod
    def fs() -> bytes:
        """^FS — Feldende (separator)."""
        return b"^FS"
    
    # === Grafik / Bild ===
    @staticmethod
    def gfa(compression_type: str, binary_byte_count: int,
            field_count: int, bytes_per_row: int, data: str) -> bytes:
        """^GF — Grafikfeld direkt in Bitmap.
        
        Args:
            compression_type: 'A' = ASCII Hex, 'B' = Binary, 'C' = Compressed
            binary_byte_count: Total bytes to transmit
            field_count: Total bytes of the image (width * height)
            bytes_per_row: Bytes per row
            data: Image data as string
        """
        return f"^GF{compression_type},{binary_byte_count},{field_count},{bytes_per_row},{data}".encode()
    
    # === Kopien / Anzahl ===
    @staticmethod
    def pq(copies: int) -> bytes:
        """^PQ — Print Quantity (Anzahl Kopien)."""
        return f"^PQ{copies}".encode()
    
    # === Druckdichte ===
    @staticmethod
    def mt_direct() -> bytes:
        """^MTD — Direct Thermal."""
        return b"^MTD"
    
    @staticmethod
    def mt_thermal_transfer() -> bytes:
        """^MTT — Thermal Transfer."""
        return b"^MTT"
    
    # === Host-Status ===
    CMD_HOST_STATUS = b"~HS\r\n"

    @staticmethod
    def sd(darkness: int) -> bytes:
        """~SD — absolute Druckdunkelheit setzen.

        Zebra dokumentiert `~SD` als absoluten Darkness-Wert im Bereich
        00 bis 30.
        """
        darkness = max(0, min(int(darkness), 30))
        return f"~SD{darkness:02d}\r\n".encode()
    
    # === SGD Wrapper ===
    @staticmethod
    def sgd_get(var_name: str) -> bytes:
        """SGD getvar-Befehl als Bytes."""
        return f'! U1 getvar "{var_name}"\r\n'.encode()
    
    @staticmethod
    def sgd_set(var_name: str, value: str) -> bytes:
        """SGD setvar-Befehl als Bytes."""
        return f'! U1 setvar "{var_name}" "{value}"\r\n'.encode()
    
    @staticmethod
    def sgd_do(action: str, value: str = "") -> bytes:
        """SGD do-Befehl als Bytes."""
        if value:
            return f'! U1 do "{action}" "{value}"\r\n'.encode()
        return f'! U1 do "{action}" ""\r\n'.encode()


def image_to_zpl_ascii_hex(image_bytes: bytes, width_bytes: int, height: int) -> str:
    """Wandle 1-Bit-Rohdaten in ASCII-Hex für ^GF.
    
    Args:
        image_bytes: 1-Bit Rohdaten (width_bytes * height Bytes)
        width_bytes: Bytes pro Zeile
        height: Anzahl Zeilen
        
    Returns:
        ASCII-Hex-String ohne Linebreaks
    """
    return image_bytes.hex()


def image_to_zpl_zb64(image_bytes: bytes) -> str:
    """Zukünftige ZB64-Kodierung für ^GF (später)."""
    raise NotImplementedError("ZB64 encoding not yet implemented")