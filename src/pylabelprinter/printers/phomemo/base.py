"""
Phomemo Drucker-Basisklasse.

Gemeinsames Protokoll für alle Phomemo Label-Drucker (M120, M221, etc.).
Modellspezifische Unterschiede (Druckbreite, Kompression) werden über
Template Methods in den Subklassen implementiert.
"""

import time
import os
from abc import abstractmethod
from typing import List, Optional, Union

from PIL import Image

from ...printer import Printer, PrinterInfo
from ...connection import UsbConnection
from ...enums import PaperType, AutoOffTime, Alignment, PrintDensity
from ...exceptions import NoPaperError, PrinterStandbyError
from ...label import Label

from .protocol import PhomemoProtocol, image_to_raw


def probe_phomemo_usb(device_path: str) -> dict:
    """Treiber-spezifische Probe für Phomemo USB-Drucker.

    Liefert optionale Zusatzinfos wie Seriennummer.
    Fehler werden nach außen propagiert.
    """
    fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
    try:
        # Buffer leeren
        try:
            while True:
                data = os.read(fd, 1024)
                if not data:
                    break
        except BlockingIOError:
            pass

        # Query Serial (Phomemo-Protokoll: 0x1F 0x11 0x09)
        os.write(fd, bytes([0x1F, 0x11, 0x09]))
        time.sleep(0.15)

        try:
            resp = os.read(fd, 64)
            if len(resp) > 2 and resp[0] == 0x1A:
                serial = resp[2:].decode("ascii", errors="ignore").rstrip("\x00")
                return {"serial_number": serial}
        except BlockingIOError:
            pass
    finally:
        os.close(fd)

    return {}


class PhomemoPrinter(Printer):
    """Abstrakte Basisklasse für alle Phomemo Label-Drucker.
    
    Implementiert das gemeinsame Phomemo-Protokoll:
        - Query/Response-Format (1F 11 CMD / 1A CMD DATA)
        - Set-Befehle (1B 4E SUB_CMD VALUE)
        - Info-Abfragen (Firmware, SN, Batterie, Papier, etc.)
        - Settings (Papierart, Auto-Off, Druckdichte)
        - Druckablauf (Template Method Pattern)
    
    Subklassen müssen definieren:
        - Hardware-Konstanten (_MODEL, _MAX_WIDTH_MM, _MAX_WIDTH_DOTS, etc.)
        - _encode_print_data() — Bilddaten-Encoding (raw vs. komprimiert)
        - _send_print_sequence() — Druckbefehl-Sequenz
    """
    
    # Hardware-Konstanten (in Subklassen überschreiben)
    _MODEL: str = ""
    _MANUFACTURER: str = "Phomemo"
    _DPI: int = 203
    _MAX_WIDTH_MM: float = 0
    _MAX_WIDTH_DOTS: int = 0
    _DEFAULT_ALIGNMENT: Alignment = Alignment.CENTER
    _SUPPORTED_PAPER_TYPES: List[PaperType] = [
        PaperType.CONTINUOUS,
        PaperType.GAP,
        PaperType.BLACK_MARK,
    ]
    _SUPPORTED_DENSITIES: List[PrintDensity] = [
        PrintDensity.LIGHT,
        PrintDensity.MEDIUM_LIGHT,
        PrintDensity.MEDIUM,
        PrintDensity.MEDIUM_DARK,
        PrintDensity.DARK,
    ]
    
    # === Factory Methods ===

    def __init__(self, connection):
        super().__init__(connection)
    
    @classmethod
    def find_usb(cls, device_path: Optional[str] = None) -> "PhomemoPrinter":
        """Finde und erstelle Drucker von USB-Gerät.
        
        Args:
            device_path: Spezifischer Gerätepfad (z.B. /dev/usb/lp0).
                        Wenn None, wird /dev/usb/lp0 verwendet.
        
        Returns:
            Drucker-Instanz (noch nicht verbunden).
        """
        if device_path is None:
            device_path = "/dev/usb/lp0"
        
        conn = UsbConnection(device_path)
        return cls(conn)
    
    # === Properties (aus Konstanten) ===
    
    @property
    def model(self) -> str:
        return self._MODEL
    
    @property
    def manufacturer(self) -> str:
        return self._MANUFACTURER
    
    @property
    def max_width_mm(self) -> float:
        return self._MAX_WIDTH_MM
    
    @property
    def dpi(self) -> int:
        return self._DPI
    
    @property
    def supported_paper_types(self) -> List[PaperType]:
        return self._SUPPORTED_PAPER_TYPES.copy()
    
    @property
    def supported_densities(self) -> List[PrintDensity]:
        return self._SUPPORTED_DENSITIES.copy()
    
    # === Query Helpers ===
    
    def _query(self, cmd: int) -> bytes:
        """Sende Query-Command und erhalte Antwort."""
        command = PhomemoProtocol.PREFIX_QUERY + bytes([cmd])
        return self._conn.query(command)
    
    def _check_awake(self) -> None:
        """Prüfe ob Drucker wach ist, sonst Exception."""
        resp = self._query(PhomemoProtocol.CMD_FIRMWARE)
        if len(resp) < 3:
            raise PrinterStandbyError(
                "Drucker antwortet nicht - vermutlich im Standby. "
                "Bitte Drucker per Knopfdruck aufwecken."
            )
    
    @property
    def is_awake(self) -> bool:
        """Prüfe ob Drucker wach ist und antwortet."""
        resp = self._query(PhomemoProtocol.CMD_FIRMWARE)
        return len(resp) >= 3
    
    # === Info Properties ===
    
    @property
    def firmware_version(self) -> str:
        """Firmware-Version (z.B. '2.0.8')."""
        resp = self._query(PhomemoProtocol.CMD_FIRMWARE)
        if len(resp) >= 5:
            return f"{resp[2]}.{resp[3]}.{resp[4]}"
        return "unknown"
    
    @property
    def serial_number(self) -> str:
        """Seriennummer."""
        resp = self._query(PhomemoProtocol.CMD_SERIAL)
        if len(resp) > 2:
            return resp[2:].decode("ascii", errors="ignore").rstrip('\x00')
        return "unknown"
    
    @property
    def battery_level(self) -> Optional[int]:
        """Akku-Stand (0-100)."""
        resp = self._query(PhomemoProtocol.CMD_BATTERY)
        if len(resp) >= 3:
            return resp[2]
        return None
    
    @property
    def has_paper(self) -> bool:
        """Prüfe ob Papier eingelegt ist (mit Retry)."""
        for _ in range(3):
            resp = self._query(PhomemoProtocol.CMD_PAPER_STATE)
            if len(resp) >= 3:
                if bool(resp[2] & 0x01):
                    return True
            time.sleep(0.1)
        return False
    
    def get_info(self) -> PrinterInfo:
        """Hole vollständige Drucker-Informationen."""
        self._check_awake()
        return PrinterInfo(
            model=self.model,
            manufacturer=self.manufacturer,
            firmware_version=self.firmware_version,
            serial_number=self.serial_number,
            max_width_mm=self.max_width_mm,
            dpi=self.dpi,
            battery_level=self.battery_level,
            has_paper=self.has_paper,
            paper_type=self.paper_type,
            auto_off_time=self.auto_off_time,
            print_density=self.print_density,
            supported_paper_types=self.supported_paper_types,
            supported_densities=self.supported_densities,
        )
    
    # === Paper Type ===
    
    def _get_paper_type(self) -> PaperType:
        """Lese aktuelle Papierart."""
        resp = self._query(PhomemoProtocol.CMD_LABEL_TYPE)
        if len(resp) >= 3:
            return PhomemoProtocol.decode_paper_type(resp[2])
        return PaperType.GAP
    
    def _set_paper_type(self, value: PaperType) -> None:
        """Setze Papierart und triggere Auto-Locate bei Bedarf."""
        code = PhomemoProtocol.encode_paper_type(value)
        self._conn.write(PhomemoProtocol.CMD_SET_PAPER_TYPE + bytes([code]))
        time.sleep(0.05)
        # Auto-Locate für GAP/BLACK_MARK-Papier
        if value in (PaperType.GAP, PaperType.BLACK_MARK):
            self._conn.write(PhomemoProtocol.CMD_AUTO_LOCATE)
            time.sleep(0.1)
    
    # === Auto-Off ===
    
    def _get_auto_off_time(self) -> AutoOffTime:
        """Lese Auto-Abschaltzeit."""
        resp = self._query(PhomemoProtocol.CMD_AUTO_OFF)
        if len(resp) >= 3:
            return PhomemoProtocol.decode_auto_off(resp[2])
        return AutoOffTime.OFF
    
    def _set_auto_off_time(self, value: AutoOffTime) -> None:
        """Setze Auto-Abschaltzeit."""
        code = PhomemoProtocol.encode_auto_off(value)
        self._conn.write(PhomemoProtocol.CMD_SET_AUTO_OFF + bytes([code]))
    
    # === Print Density ===
    
    def _get_print_density(self) -> PrintDensity:
        """Lese aktuelle Druckdichte.
        
        Phomemo-Drucker speichern Density nicht persistent abfragbar.
        """
        return PrintDensity.MEDIUM
    
    def _set_print_density(self, value: PrintDensity) -> None:
        """Setze Druckdichte."""
        code = PhomemoProtocol.encode_density(value)
        self._conn.write(PhomemoProtocol.CMD_SET_DENSITY + bytes([code]))
    
    # === Printing (Template Method) ===
    
    def print_image(
        self,
        image: Image.Image,
        label: Label,
        copies: int = 1,
        density: Optional[Union[PrintDensity, int]] = None,
        alignment: Optional[Alignment] = None,
    ) -> None:
        """Drucke ein Bild auf ein Label.
        
        Verwendet Template Method Pattern:
        - Bildvorbereitung und Header sind gemeinsam
        - _encode_print_data() und _send_print_sequence() sind modellspezifisch
        
        Args:
            image: PIL Image (wird automatisch skaliert und konvertiert)
            label: Label-Größe
            copies: Anzahl Kopien (1-99)
            density: Druckdichte (PrintDensity enum oder int 1-15, None = aktuelle Einstellung)
            alignment: Ausrichtung auf Druckbreite
        """
        # Alignment: Standard aus Klasse wenn nicht angegeben
        if alignment is None:
            alignment = self._DEFAULT_ALIGNMENT
        
        # Papier prüfen
        if not self.has_paper:
            raise NoPaperError("No paper loaded")
        
        # Label-Größe in Dots
        label_width, label_height = label.get_size_dots(self.dpi)
        
        # Bild auf Label-Größe skalieren wenn nötig
        if image.size != (label_width, label_height):
            image = image.resize((label_width, label_height), Image.Resampling.LANCZOS)
        
        # Druckbreite (volle Druckerbreite)
        printer_width = self._MAX_WIDTH_DOTS
        
        # Alignment-Offset berechnen
        if alignment == Alignment.CENTER:
            offset_x = (printer_width - label_width) // 2
        elif alignment == Alignment.RIGHT:
            offset_x = printer_width - label_width
        else:  # LEFT
            offset_x = 0
        
        # Bild in voller Druckerbreite erstellen
        full_image = Image.new("L", (printer_width, label_height), 255)
        
        # Grayscale konvertieren wenn nötig
        if image.mode != "L":
            image = image.convert("L")
        
        # Bild einfügen
        full_image.paste(image, (offset_x, 0))
        
        # Zu Raw-Bitmap konvertieren
        raw_data = image_to_raw(full_image)
        width_bytes = printer_width // 8
        
        # Modellspezifisch: Drucksequenz senden
        self._send_print_sequence(raw_data, width_bytes, label_height, copies, density)
        
        # Warten auf Druckabschluss-Bestätigung
        self._wait_for_print_complete(timeout=10.0)
    
    @abstractmethod
    def _send_print_sequence(
        self,
        raw_data: bytes,
        width_bytes: int,
        height: int,
        copies: int,
        density: Optional[Union[PrintDensity, int]],
    ) -> None:
        """Sende die modellspezifische Druckbefehl-Sequenz.
        
        Args:
            raw_data: 1-Bit Bitmap-Daten (unkomprimiert, width_bytes pro Zeile)
            width_bytes: Breite in Bytes (Dots / 8)
            height: Höhe in Zeilen
            copies: Anzahl Kopien
            density: Druckdichte (None = nicht ändern)
        """
        ...
    
    # === Print Helpers ===
    
    def _send_density(self, density: Optional[Union[PrintDensity, int]]) -> None:
        """Setze Druckdichte wenn angegeben.
        
        Args:
            density: PrintDensity enum, int (1-15), oder None
        """
        if density is not None:
            if isinstance(density, int):
                self._conn.write(PhomemoProtocol.CMD_SET_DENSITY + bytes([density]))
            else:
                self._set_print_density(density)
            time.sleep(0.05)
    
    def _wait_for_print_complete(self, timeout: float = 10.0) -> bool:
        """Warte auf Druckabschluss-Bestätigung vom Drucker.
        
        Der Drucker sendet 0x0F 0x0C wenn der Druck abgeschlossen ist.
        
        Args:
            timeout: Maximale Wartezeit in Sekunden
            
        Returns:
            True wenn Bestätigung empfangen, False bei Timeout
        """
        end_time = time.time() + timeout
        buffer = b""
        
        while time.time() < end_time:
            try:
                data = self._conn.read(64, timeout=0.1)
                if data:
                    buffer += data
                    if PhomemoProtocol.RESPONSE_PRINT_COMPLETE in buffer:
                        return True
            except Exception:
                pass
            time.sleep(0.05)
        
        return False
    
    def feed(self) -> None:
        """Papier zum nächsten Label transportieren."""
        self._conn.write(PhomemoProtocol.CMD_FEED)
    
    def auto_locate(self) -> None:
        """Automatisch zum nächsten Label-Gap fahren."""
        self._conn.write(PhomemoProtocol.CMD_AUTO_LOCATE)
