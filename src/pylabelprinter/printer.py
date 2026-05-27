"""
Abstrakte Basis-Klassen für Drucker.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from PIL import Image

from .enums import PaperType, AutoOffTime, Alignment, PrintDensity
from .exceptions import UnsupportedFeatureError
from .label import Label, ImageSize

if TYPE_CHECKING:
    from .connection import Connection


@dataclass
class PrinterInfo:
    """Drucker-Informationen."""
    model: str
    manufacturer: str
    firmware_version: str
    serial_number: str
    max_width_mm: float
    dpi: int
    battery_level: Optional[int] = None       # 0-100, None wenn kein Akku
    has_paper: Optional[bool] = None
    paper_type: Optional[PaperType] = None
    auto_off_time: Optional[AutoOffTime] = None
    print_density: Optional[PrintDensity] = None
    supported_paper_types: Optional[List[PaperType]] = None
    supported_densities: Optional[List[PrintDensity]] = None


class Printer(ABC):
    """Abstrakte Basis-Klasse für Label-Drucker."""
    
    def __init__(self, connection: "Connection"):
        """Initialisiere Drucker mit Verbindung.
        
        Args:
            connection: Connection-Objekt (USB, Bluetooth, etc.)
        """
        self._conn = connection
        self._connected = False
    
    # === Verbindung ===
    
    def connect(self) -> None:
        """Öffne Verbindung zum Drucker."""
        self._conn.open()
        self._connected = True
    
    def disconnect(self) -> None:
        """Schließe Verbindung zum Drucker."""
        self._conn.close()
        self._connected = False
    
    def close(self) -> None:
        """Alias für disconnect()."""
        self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Prüfe ob verbunden."""
        return self._connected
    
    def __enter__(self) -> "Printer":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
    
    # === Abstrakte Properties ===
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Drucker-Modell (z.B. 'M221')."""
        ...
    
    @property
    @abstractmethod
    def manufacturer(self) -> str:
        """Hersteller (z.B. 'Phomemo')."""
        ...
    
    @property
    @abstractmethod
    def max_width_mm(self) -> float:
        """Maximale Druckbreite in mm."""
        ...
    
    @property
    @abstractmethod
    def dpi(self) -> int:
        """Auflösung in DPI."""
        ...
    
    @property
    @abstractmethod
    def supported_paper_types(self) -> List[PaperType]:
        """Liste der unterstützten Papierarten."""
        ...
    
    # === Info-Abfragen ===
    
    @abstractmethod
    def get_info(self) -> PrinterInfo:
        """Hole vollständige Drucker-Informationen."""
        ...
    
    @property
    @abstractmethod
    def firmware_version(self) -> str:
        """Firmware-Version."""
        ...
    
    @property
    @abstractmethod
    def serial_number(self) -> str:
        """Seriennummer."""
        ...
    
    @property
    def battery_level(self) -> Optional[int]:
        """Akku-Stand (0-100) oder None wenn kein Akku."""
        return None  # Default: kein Akku
    
    @property
    @abstractmethod
    def has_paper(self) -> bool:
        """Prüfe ob Papier eingelegt ist."""
        ...
    
    # === Paper Type ===
    
    @property
    def paper_type(self) -> PaperType:
        """Aktuelle Papierart abfragen."""
        return self._get_paper_type()
    
    @paper_type.setter
    def paper_type(self, value: PaperType) -> None:
        """Papierart setzen mit Validierung."""
        if value not in self.supported_paper_types:
            supported = [p.name for p in self.supported_paper_types]
            raise UnsupportedFeatureError(
                f"Paper type {value.name} not supported. "
                f"Supported: {supported}"
            )
        self._set_paper_type(value)
    
    @abstractmethod
    def _get_paper_type(self) -> PaperType:
        """Interne Methode: Papierart lesen."""
        ...
    
    @abstractmethod
    def _set_paper_type(self, value: PaperType) -> None:
        """Interne Methode: Papierart setzen."""
        ...
    
    # === Auto-Off ===
    
    @property
    def auto_off_time(self) -> AutoOffTime:
        """Aktuelle Auto-Abschaltzeit."""
        return self._get_auto_off_time()
    
    @auto_off_time.setter
    def auto_off_time(self, value: AutoOffTime) -> None:
        """Auto-Abschaltzeit setzen."""
        self._set_auto_off_time(value)
    
    def _get_auto_off_time(self) -> AutoOffTime:
        """Interne Methode: Auto-Off lesen. Override wenn unterstützt."""
        raise UnsupportedFeatureError("Auto-off not supported")
    
    def _set_auto_off_time(self, value: AutoOffTime) -> None:
        """Interne Methode: Auto-Off setzen. Override wenn unterstützt."""
        raise UnsupportedFeatureError("Auto-off not supported")
    
    # === Print Density ===
    
    @property
    def supported_densities(self) -> List[PrintDensity]:
        """Liste der unterstützten Druckdichten."""
        return []  # Default: keine Dichte-Einstellung
    
    @property
    def print_density(self) -> PrintDensity:
        """Aktuelle Druckdichte."""
        return self._get_print_density()
    
    @print_density.setter
    def print_density(self, value: PrintDensity) -> None:
        """Druckdichte setzen mit Validierung."""
        if value not in self.supported_densities:
            supported = [d.name for d in self.supported_densities]
            raise UnsupportedFeatureError(
                f"Print density {value.name} not supported. "
                f"Supported: {supported}"
            )
        self._set_print_density(value)
    
    def _get_print_density(self) -> PrintDensity:
        """Interne Methode: Dichte lesen. Override wenn unterstützt."""
        raise UnsupportedFeatureError("Print density setting not supported")
    
    def _set_print_density(self, value: PrintDensity) -> None:
        """Interne Methode: Dichte setzen. Override wenn unterstützt."""
        raise UnsupportedFeatureError("Print density setting not supported")
    
    # === Label/Image Größe ===
    
    def get_image_size(self, label: Label) -> ImageSize:
        """Berechne Bildgröße für ein Label.
        
        Args:
            label: Label-Definition
            
        Returns:
            ImageSize mit Pixel-Dimensionen für diesen Drucker.
        """
        width, height = label.get_size_dots(self.dpi)
        return ImageSize(
            width=width,
            height=height,
            dpi=self.dpi,
            label=label
        )
    
    # === Drucken ===
    
    @abstractmethod
    def print_image(
        self,
        image: Image.Image,
        label: Label,
        copies: int = 1,
        density: Optional[PrintDensity] = None,
        alignment: Alignment = Alignment.CENTER,
    ) -> None:
        """Drucke ein Bild auf ein Label.
        
        Args:
            image: PIL Image (wird automatisch konvertiert)
            label: Label-Größe
            copies: Anzahl Kopien
            density: Druckdichte (None = aktuelle Einstellung beibehalten)
            alignment: Ausrichtung auf Druckbreite
        """
        ...
    
    @abstractmethod
    def feed(self) -> None:
        """Papier zum nächsten Label transportieren."""
        ...
