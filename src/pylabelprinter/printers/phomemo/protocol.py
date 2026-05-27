"""
Phomemo-Protokoll: Commands, Mappings, Kompression.
"""

import lzo
from typing import Dict

from ...enums import PaperType, AutoOffTime, PrintDensity
from ...exceptions import UnsupportedFeatureError


class PhomemoProtocol:
    """Phomemo-spezifische Protokoll-Konstanten und Mappings."""
    
    # === Command Prefixes ===
    PREFIX_QUERY = bytes([0x1F, 0x11])
    PREFIX_RESPONSE = 0x1A
    
    # === Query Commands ===
    CMD_FIRMWARE = 0x07
    CMD_BATTERY = 0x08
    CMD_SERIAL = 0x09
    CMD_AUTO_OFF = 0x0E
    CMD_PAPER_STATE = 0x11
    CMD_COVER_STATE = 0x12
    CMD_LABEL_TYPE = 0x19
    
    # === Set Commands ===
    CMD_SET_PAPER_TYPE = bytes([0x1F, 0x11])
    CMD_SET_DENSITY = bytes([0x1B, 0x4E, 0x04])
    CMD_SET_AUTO_OFF = bytes([0x1B, 0x4E, 0x07])
    CMD_INIT_PRINTER = bytes([0x1B, 0x40])
    CMD_ENTER_COMPRESS = bytes([0x1F, 0x11, 0x35, 0x01])
    CMD_EXIT_COMPRESS = bytes([0x1F, 0x11, 0x35, 0x00])
    CMD_PRINT_MULTI = bytes([0x1F, 0x11, 0x21])
    CMD_PRINT_IMAGE = bytes([0x1D, 0x76, 0x30, 0x00])
    CMD_FEED = bytes([0x1F, 0x11, 0x32])
    CMD_AUTO_LOCATE = bytes([0x1F, 0x11, 0x25])
    
    # === Response Bytes ===
    RESPONSE_PRINT_COMPLETE = bytes([0x0F, 0x0C])  # Druck abgeschlossen
    RESPONSE_NO_PAPER = bytes([0x06, 0x88])        # Kein Papier
    
    # === Mappings: Generisch → Phomemo-Byte ===
    
    PAPER_TYPE_MAP: Dict[PaperType, int] = {
        # Werte entsprechen den internen Sensor/Set-Codes
        PaperType.CONTINUOUS: 0x0B,
        PaperType.GAP: 0x0A,
        PaperType.BLACK_MARK: 0x26,
    }
    
    # Internes Format (aus Sensor-Abfrage)
    PAPER_TYPE_INTERNAL_MAP: Dict[int, PaperType] = {
        10: PaperType.GAP,          # Intermittent/Hole (App nutzt 0x0A)
        11: PaperType.CONTINUOUS,
        12: PaperType.GAP,
        38: PaperType.BLACK_MARK,
    }
    
    AUTO_OFF_MAP: Dict[AutoOffTime, int] = {
        AutoOffTime.OFF: 0,
        AutoOffTime.MIN_1: 1,
        AutoOffTime.MIN_5: 2,
        AutoOffTime.MIN_10: 3,
        AutoOffTime.MIN_15: 4,
        AutoOffTime.MIN_20: 5,
        AutoOffTime.MIN_30: 6,
        AutoOffTime.MIN_60: 7,
        AutoOffTime.MIN_120: 8,
    }
    
    AUTO_OFF_REVERSE_MAP: Dict[int, AutoOffTime] = {
        v: k for k, v in AUTO_OFF_MAP.items()
    }
    
    # Print density mapping (from PrefConstants.java)
    # Steuert Thermokopf-Hitze = Druckschwärze
    DENSITY_MAP: Dict[PrintDensity, int] = {
        PrintDensity.LIGHT: 1,         # TYPE_CONCENTRATION_LIGHT
        PrintDensity.MEDIUM_LIGHT: 2,  # TYPE_CONCENTRATION_STANDARD
        PrintDensity.MEDIUM: 6,        # TYPE_CONCENTRATION_NORMAL
        PrintDensity.MEDIUM_DARK: 4,   # TYPE_CONCENTRATION_STRONG
        PrintDensity.DARK: 13,         # TYPE_CONCENTRATION_DARK
    }
    
    DENSITY_REVERSE_MAP: Dict[int, PrintDensity] = {
        v: k for k, v in DENSITY_MAP.items()
    }
    
    # === Encoding/Decoding ===
    
    @classmethod
    def encode_paper_type(cls, paper_type: PaperType) -> int:
        """Konvertiere generischen PaperType zu Phomemo-Byte."""
        if paper_type not in cls.PAPER_TYPE_MAP:
            raise UnsupportedFeatureError(
                f"Paper type {paper_type.name} not supported by Phomemo printers"
            )
        return cls.PAPER_TYPE_MAP[paper_type]
    
    @classmethod
    def decode_paper_type(cls, value: int) -> PaperType:
        """Konvertiere Phomemo-internen Wert zu generischem PaperType."""
        if value in cls.PAPER_TYPE_INTERNAL_MAP:
            return cls.PAPER_TYPE_INTERNAL_MAP[value]
        # Fallback
        return PaperType.GAP
    
    @classmethod
    def encode_auto_off(cls, auto_off: AutoOffTime) -> int:
        """Konvertiere generischen AutoOffTime zu Phomemo-Byte."""
        if auto_off not in cls.AUTO_OFF_MAP:
            raise UnsupportedFeatureError(
                f"Auto-off time {auto_off.name} not supported"
            )
        return cls.AUTO_OFF_MAP[auto_off]
    
    @classmethod
    def decode_auto_off(cls, value: int) -> AutoOffTime:
        """Konvertiere Phomemo-Byte zu generischem AutoOffTime."""
        return cls.AUTO_OFF_REVERSE_MAP.get(value, AutoOffTime.OFF)
    
    @classmethod
    def encode_density(cls, density: PrintDensity) -> int:
        """Konvertiere generischen PrintDensity zu Phomemo-Byte."""
        if density not in cls.DENSITY_MAP:
            raise UnsupportedFeatureError(
                f"Print density {density.name} not supported"
            )
        return cls.DENSITY_MAP[density]
    
    @classmethod
    def decode_density(cls, value: int) -> PrintDensity:
        """Konvertiere Phomemo-Byte zu generischem PrintDensity."""
        return cls.DENSITY_REVERSE_MAP.get(value, PrintDensity.MEDIUM)


def minilzo_compress(data: bytes, block_size: int = 4096) -> bytes:
    """Komprimiere Daten im Phomemo MiniLZO-Format.
    
    Daten werden in Blöcken komprimiert, jeder Block mit 3-Byte Längenprefix.
    
    Args:
        data: Unkomprimierte Daten
        block_size: Blockgröße (Standard: 4096)
        
    Returns:
        Komprimierte Daten im Phomemo-Format
    """
    result = bytearray()
    offset = 0
    
    while offset < len(data):
        chunk = data[offset:offset + block_size]
        offset += len(chunk)
        
        # LZO komprimieren (ohne Header)
        compressed = lzo.compress(bytes(chunk), 1, False)
        
        # Länge als 3-Byte Little-Endian
        length = len(compressed)
        result.append(length & 0xFF)
        result.append((length >> 8) & 0xFF)
        result.append((length >> 16) & 0xFF)
        result.extend(compressed)
    
    return bytes(result)


def image_to_raw(image, threshold: int = 127) -> bytes:
    """Konvertiere PIL Image zu Raw-Bitmap-Daten.
    
    Args:
        image: PIL Image (wird zu Grayscale konvertiert)
        threshold: Schwellwert für Schwarz/Weiß (0-255)
        
    Returns:
        Gepackte 1-Bit Bitmap-Daten (MSB first, Schwarz = 1)
    """
    # Zu Grayscale konvertieren
    if image.mode != "L":
        image = image.convert("L")
    
    width, height = image.size
    
    raw_data = bytearray()
    
    for y in range(height):
        byte_val = 0
        bit_count = 0
        
        for x in range(width):
            pixel = image.getpixel((x, y))
            
            # Pixel < threshold = Schwarz = 1 (wird gedruckt)
            if pixel < threshold:
                byte_val = (byte_val << 1) | 1
            else:
                byte_val = byte_val << 1
            
            bit_count += 1
            
            if bit_count == 8:
                raw_data.append(byte_val)
                byte_val = 0
                bit_count = 0
        
        # Rest der Zeile mit Nullen auffüllen (sollte nicht passieren bei korrekter Breite)
        if bit_count > 0:
            byte_val = byte_val << (8 - bit_count)
            raw_data.append(byte_val)
    
    return bytes(raw_data)
