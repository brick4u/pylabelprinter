"""
Zebra-Drucker Basisklasse.

Gemeinsames Protokoll für Zebra-Label-Drucker der ZD-Serie.
ZPL und SGD werden als textbasierte Kommandosprache über den
USB-Bulk-Endpoint gesendet.
"""

import os
import time
from typing import List, Optional, Union

from PIL import Image

from ...printer import Printer, PrinterInfo
from ...connection import UsbConnection
from ...enums import PaperType, Alignment, PrintDensity, PrintTechnology
from ...exceptions import NoPaperError
from ...label import Label

from .protocol import ZPL, image_to_zpl_ascii_hex


def _normalize_sgd_value(value: str) -> str:
    """Normalisiere Zebra-SGD-Antworten.

    Zebra liefert String-Werte typischerweise in doppelten Anführungszeichen
    zurück. Diese äußeren Quotes werden entfernt.
    """
    value = value.strip().rstrip("\x00\n\r")
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def probe_zebra_usb(device_path: str) -> dict:
    """Treiber-spezifische Probe für Zebra USB-Drucker.
    
    Sendet einen SGD-getvar, um Seriennummer zu ermitteln.
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

        # Serial Number über SGD abfragen
        os.write(fd, ZPL.sgd_get("device.unique_id"))
        deadline = time.time() + 0.75
        buffer = bytearray()

        while time.time() < deadline:
            try:
                resp = os.read(fd, 256)
                if resp:
                    buffer.extend(resp)
                    sn = _normalize_sgd_value(buffer.decode("ascii", errors="ignore"))
                    if sn:
                        return {"serial_number": sn}
                else:
                    break
            except BlockingIOError:
                time.sleep(0.02)
    finally:
        os.close(fd)

    return {}


class ZebraPrinter(Printer):
    """Abstrakte Basisklasse für Zebra Label-Drucker.
    
    Implementiert das gemeinsame ZPL-Protokoll:
        - Label-Format via ^XA ... ^XZ
        - Grafik via ^GF (ASCII-Hex)
        - Status via SGD und ~HS
        - Konfiguration via SGD setvar/getvar
    
    Subklassen müssen definieren:
        - Hardware-Konstanten (_MODEL, _MAX_WIDTH_MM, _MAX_WIDTH_DOTS, etc.)
    """
    
    # Hardware-Konstanten (in Subklassen überschreiben)
    _MODEL: str = ""
    _MANUFACTURER: str = "Zebra Technologies"
    _DPI: int = 203
    _MAX_WIDTH_MM: float = 0
    _MAX_WIDTH_DOTS: int = 0
    _DEFAULT_ALIGNMENT: Alignment = Alignment.CENTER
    _SUPPORTED_PAPER_TYPES: List[PaperType] = [
        PaperType.AUTO_DETECT,
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
    _SUPPORTED_PRINT_TECHNOLOGIES: List[PrintTechnology] = [
        PrintTechnology.DIRECT_THERMAL,
    ]
    _USB_WRITE_CHUNK_SIZE: int = 65536
    _USB_WRITE_CHUNK_DELAY: float = 0.0
    _USB_WRITE_RETRY_DELAY: float = 0.01
    
    def __init__(self, connection):
        super().__init__(connection)
    
    @classmethod
    def find_usb(cls, device_path: Optional[str] = None) -> "ZebraPrinter":
        """Finde und erstelle Drucker von USB-Gerät.
        
        Args:
            device_path: Spezifischer Gerätepfad (z.B. /dev/usb/lp0).
                        Wenn None, wird /dev/usb/lp0 verwendet.
        
        Returns:
            Drucker-Instanz (noch nicht verbunden).
        """
        if device_path is None:
            device_path = "/dev/usb/lp0"
        conn = UsbConnection(
            device_path,
            write_chunk_size=cls._USB_WRITE_CHUNK_SIZE,
            write_chunk_delay=cls._USB_WRITE_CHUNK_DELAY,
            write_retry_delay=cls._USB_WRITE_RETRY_DELAY,
        )
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
    
    @property
    def supported_print_technologies(self) -> List[PrintTechnology]:
        return list(self._SUPPORTED_PRINT_TECHNOLOGIES)
    
    # === SGD Query Helper ===
    
    def _sgd_query(self, var: str) -> Optional[str]:
        """Sende SGD-getvar und lese Antwort.
        
        Args:
            var: SGD-Variablenname (z.B. "device.unique_id")
            
        Returns:
            Antwort-String oder None bei Timeout
        """
        self._conn.flush_input()
        cmd = ZPL.sgd_get(var)
        self._conn.write(cmd)
        deadline = time.time() + 1.0
        buffer = bytearray()

        while time.time() < deadline:
            remaining = max(0.0, deadline - time.time())
            resp = self._conn.read(256, timeout=min(0.2, remaining))
            if not resp:
                continue

            buffer.extend(resp)
            text = buffer.decode("ascii", errors="ignore")

            # Zebra antwortet für Stringwerte typischerweise mit quoted strings.
            # Bei fragmentierten Reads erst zurückgeben, wenn die Antwort
            # vollständig aussieht.
            stripped = text.strip().rstrip("\x00")
            if stripped.startswith('"') and not stripped.endswith('"'):
                continue

            value = _normalize_sgd_value(text)
            if value:
                return value

        return None

    def _read_host_status_fields(self, timeout: float = 1.0) -> Optional[List[str]]:
        """Lese den ersten `~HS`-Status-String und zerlege ihn in Felder.

        Laut Zebra-Doku liefert `~HS` drei Strings zurück, jeweils eingerahmt
        von `<STX>` und `<ETX><CR><LF>`. In mehreren Fehlerzuständen kann der
        Drucker auf `~HS` auch gar nicht antworten. In diesem Fall wird `None`
        zurückgegeben.
        """
        self._conn.flush_input()
        self._conn.write(ZPL.CMD_HOST_STATUS)

        deadline = time.time() + timeout
        buffer = bytearray()

        while time.time() < deadline:
            remaining = max(0.0, deadline - time.time())
            chunk = self._conn.read(512, timeout=min(0.2, remaining))
            if not chunk:
                continue

            buffer.extend(chunk)

            start = buffer.find(b"\x02")
            end = buffer.find(b"\x03", start + 1 if start != -1 else 0)
            if start != -1 and end != -1 and end > start:
                payload = bytes(buffer[start + 1:end])
                text = payload.decode("ascii", errors="ignore").strip()
                if text:
                    return [field.strip() for field in text.split(",")]

        return None
    
    # === Info Properties ===
    
    @property
    def firmware_version(self) -> str:
        """Firmware-Version über SGD."""
        result = self._sgd_query("appl.name")
        return result or "unknown"
    
    @property
    def serial_number(self) -> str:
        """Seriennummer über SGD."""
        result = self._sgd_query("device.unique_id")
        return result or "unknown"
    
    @property
    def has_paper(self) -> bool:
        """Prüfe ob Papier eingelegt ist über ~HS.

        ~HS String 1 Format: <STX>aaa,b,c,...<ETX>
            b = paper out flag (1 = paper out)
        """
        fields = self._read_host_status_fields(timeout=1.0)

        # Laut Zebra-Doku kann `~HS` bei MEDIA OUT und weiteren Fehlerzuständen
        # ohne Antwort bleiben. Das darf nicht als "Papier vorhanden" gewertet
        # werden.
        if not fields or len(fields) < 2:
            return False

        # b (2. Feld) = paper out flag (1 = paper out)
        return fields[1] != "1"
    
    def get_info(self) -> PrinterInfo:
        """Hole vollständige Drucker-Informationen.

        Datenblatt-Felder (aus Klassenkonstanten, kein Live-Query):
            model, manufacturer, max_width_mm, dpi,
            supported_paper_types, supported_densities

        Live abgefragte Felder (via SGD / ~HS):
            firmware_version (SGD appl.name)
            serial_number (SGD device.unique_id)
            has_paper (~HS Host-Status)
            paper_type (SGD ezpl.media_type)

        Nicht unterstützt (None):
            battery_level (Desktop-Netzteil, kein Akku)
            auto_off_time (weder via SGD noch ZPL konfigurierbar)
        """
        return PrinterInfo(
            # === Datenblatt (Klassenkonstanten) ===
            model=self.model,
            manufacturer=self.manufacturer,
            max_width_mm=self.max_width_mm,
            dpi=self.dpi,
            supported_paper_types=self.supported_paper_types,
            supported_densities=self.supported_densities,
            # === Datenblatt (unterstützte Verfahren) ===
            supported_print_technologies=self.supported_print_technologies,
            print_technology=self.print_technology,
            # === Live (via SGD / ~HS) ===
            firmware_version=self.firmware_version,
            serial_number=self.serial_number,
            has_paper=self.has_paper,
            paper_type=self.paper_type,
            # === Nicht unterstützt ===
            battery_level=None,
            auto_off_time=None,
            print_density=None,
        )
    
    # === Paper Type ===
    
    def _get_paper_type(self) -> PaperType:
        """Lese aktuelle Papierart via SGD."""
        result = self._sgd_query("ezpl.media_type")
        if result:
            value = result.lower()
            if value == "auto_detect":
                return PaperType.AUTO_DETECT
            if "mark" in value or "black" in value:
                return PaperType.BLACK_MARK
            elif "gap" in value or "notch" in value:
                return PaperType.GAP
        return PaperType.CONTINUOUS
    
    def _set_paper_type(self, value: PaperType) -> None:
        """Setze Papierart via SGD."""
        mapping = {
            PaperType.AUTO_DETECT: "auto_detect",
            PaperType.CONTINUOUS: "continuous",
            PaperType.GAP: "gap/notch",
            PaperType.BLACK_MARK: "mark",
        }
        if value in mapping:
            cmd = ZPL.sgd_set("ezpl.media_type", mapping[value])
            self._conn.write(cmd)
            time.sleep(0.1)
    
    # === Auto-Off ===
    # Zebra-Drucker haben typischerweise kein konfigurierbares Auto-Off
    # (im Gegensatz zu Phomemo). Daher: nicht unterstützt.
    
    # === Print Density ===
    
    def _get_print_density(self) -> PrintDensity:
        """Zebra hat keine DPI/Hitze-Abfrage → Standardwert."""
        return PrintDensity.MEDIUM
    
    def _set_print_density(self, value: PrintDensity) -> None:
        """Setze Druckdichte über absoluten Zebra-Darkness-Wert."""
        density_map = {
            PrintDensity.LIGHT: 5,
            PrintDensity.MEDIUM_LIGHT: 10,
            PrintDensity.MEDIUM: 15,
            PrintDensity.MEDIUM_DARK: 20,
            PrintDensity.DARK: 30,
        }
        val = density_map.get(value, 15)
        self._conn.write(ZPL.sd(val))
        time.sleep(0.05)

    def _get_print_technology(self) -> PrintTechnology:
        """Lese das aktuell konfigurierte Druckverfahren via SGD."""
        result = self._sgd_query("ezpl.print_method")
        if result:
            value = result.strip().lower()
            if "direct" in value:
                return PrintTechnology.DIRECT_THERMAL
            if "thermal trans" in value or "transfer" in value:
                return PrintTechnology.THERMAL_TRANSFER

        return super()._get_print_technology()

    def _set_print_technology(self, value: PrintTechnology) -> None:
        """Setze das Druckverfahren via SGD."""
        mapping = {
            PrintTechnology.DIRECT_THERMAL: "direct thermal",
            PrintTechnology.THERMAL_TRANSFER: "thermal trans",
        }
        cmd_value = mapping.get(value)
        if cmd_value is None:
            raise ValueError(f"Unsupported print technology: {value}")
        self._conn.write(ZPL.sgd_set("ezpl.print_method", cmd_value))
        time.sleep(0.1)
    
    # === Drucken ===
    
    def print_image(
        self,
        image: Image.Image,
        label: Label,
        copies: int = 1,
        density: Optional[Union[PrintDensity, int]] = None,
        alignment: Optional[Alignment] = None,
        x_offset_mm: float = 0.0,
        y_offset_mm: float = 0.0,
    ) -> None:
        """Drucke ein Bild auf ein Label via ZPL.
        
        Das Bild wird in ASCII-Hex kodiert und als ^GF-Grafikfeld in
        ein ZPL-Format eingebettet.
        
        Args:
            image: PIL Image (wird automatisch skaliert und konvertiert)
            label: Label-Größe
            copies: Anzahl Kopien (1-999)
            density: Druckdichte (PrintDensity enum oder None)
            alignment: Ausrichtung auf Druckbreite
            x_offset_mm: Horizontaler Offset in mm (positiv = rechts)
            y_offset_mm: Vertikaler Offset in mm (positiv = unten)
        """
        if alignment is None:
            alignment = self._DEFAULT_ALIGNMENT
        
        # Papier prüfen
        if not self.has_paper:
            raise NoPaperError("No paper loaded")
        
        # Label-Größe in Dots
        label_width, label_height = label.get_size_dots(self.dpi)
        printer_width = self._MAX_WIDTH_DOTS
        
        # Offset mm → Dots
        x_offset_dots = int(x_offset_mm * self.dpi / 25.4)
        y_offset_dots = int(y_offset_mm * self.dpi / 25.4)
        
        # Bild skalieren
        if image.size != (label_width, label_height):
            image = image.resize((label_width, label_height), Image.Resampling.LANCZOS)
        
        # Alignment + X-Offset → ^FO x
        if alignment == Alignment.CENTER:
            fo_x = (printer_width - label_width) // 2 + x_offset_dots
        elif alignment == Alignment.RIGHT:
            fo_x = printer_width - label_width + x_offset_dots
        else:
            fo_x = x_offset_dots
        
        # Y-Offset → ^FO y
        fo_y = y_offset_dots
        
        # Kein Vollbreiten-Canvas: Bild in Labelgröße belassen,
        # X-Positionierung erfolgt im ZPL via ^FO
        if image.mode != "L":
            image = image.convert("L")
        
        # Nach 1-Bit konvertieren und invertieren
        bw_image = image.point(lambda x: 0 if x < 128 else 255, "1")
        raw_bytes = bw_image.tobytes()
        raw_bytes = bytes(~b & 0xFF for b in raw_bytes)
        
        width_bytes = (label_width + 7) // 8
        total_bytes = width_bytes * label_height
        
        # ASCII-Hex für ^GF
        hex_data = image_to_zpl_ascii_hex(raw_bytes, width_bytes, label_height)
        
        # Dichte setzen falls angegeben (absolut via ~SD)
        if density is not None:
            if isinstance(density, PrintDensity):
                self._set_print_density(density)
            else:
                val = max(0, min(int(density), 30))
                self._conn.write(ZPL.sd(val))
                time.sleep(0.05)
        
        # ZPL-Format bauen
        zpl_lines = [
            b"^XA",
            b"^PR2",
            ZPL.pw(printer_width),
            ZPL.ll(label_height),
            b"^CI0",  # Codepage: Latin-1
        ]
        
        # Grafikfeld einfügen (Positionierung via ^FO = Alignment + Offset)
        zpl_lines.append(ZPL.fo(fo_x, fo_y))
        zpl_lines.append(
            f"^GFA,{total_bytes},{total_bytes},{width_bytes},".encode() + hex_data.encode()
        )
        
        # Kopienanzahl immer angeben
        zpl_lines.append(ZPL.pq(copies))
        zpl_lines.append(b"^XZ")
        
        # Mit CRLF verbinden; für ZPL nicht zwingend erforderlich, aber gut lesbar
        # und in der Praxis unproblematisch.
        zpl_output = b"\r\n".join(zpl_lines) + b"\r\n"
        self._conn.write(zpl_output)
        
        time.sleep(0.5)
    
    def feed(self) -> None:
        """Papier zum nächsten Label transportieren via ~PF."""
        self._conn.write(b"~PF\r\n")
        time.sleep(0.1)