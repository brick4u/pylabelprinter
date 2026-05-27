"""
Label-Definitionen und Größenberechnungen.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Label:
    """Label-Größe in Millimetern."""
    width_mm: float
    height_mm: float
    
    def get_size_dots(self, dpi: int = 203) -> Tuple[int, int]:
        """Berechne Pixel-Dimensionen für gegebene DPI.
        
        Args:
            dpi: Auflösung in Dots Per Inch (Standard: 203 für Thermodrucker)
            
        Returns:
            Tuple (width_dots, height_dots)
        """
        dots_per_mm = dpi / 25.4
        return (
            int(self.width_mm * dots_per_mm),
            int(self.height_mm * dots_per_mm)
        )
    
    # Vordefinierte Standardgrößen
    @classmethod
    def SIZE_30x20(cls) -> "Label":
        """30x20mm Label."""
        return cls(30, 20)
    
    @classmethod
    def SIZE_40x30(cls) -> "Label":
        """40x30mm Label."""
        return cls(40, 30)
    
    @classmethod
    def SIZE_50x30(cls) -> "Label":
        """50x30mm Label."""
        return cls(50, 30)
    
    @classmethod
    def SIZE_50x40(cls) -> "Label":
        """50x40mm Label."""
        return cls(50, 40)
    
    @classmethod
    def SIZE_60x40(cls) -> "Label":
        """60x40mm Label."""
        return cls(60, 40)
    
    @classmethod 
    def SIZE_70x50(cls) -> "Label":
        """70x50mm Label."""
        return cls(70, 50)
    
    def __str__(self) -> str:
        return f"{self.width_mm}x{self.height_mm}mm"


@dataclass(frozen=True)
class ImageSize:
    """Bild-Dimensionen für ein Label."""
    width: int          # Pixel
    height: int         # Pixel
    dpi: int            # Auflösung
    label: Label        # Ursprüngliches Label
    
    @property
    def bytes_uncompressed(self) -> int:
        """Größe in Bytes (unkomprimiert, 1-bit)."""
        return (self.width * self.height) // 8
    
    def __str__(self) -> str:
        return f"{self.width}x{self.height}px @ {self.dpi} DPI ({self.label})"


def get_image_size(label: Label, dpi: int = 203) -> ImageSize:
    """Berechne Bildgröße für ein Label.
    
    Args:
        label: Label-Definition
        dpi: Drucker-Auflösung (Standard: 203 DPI)
        
    Returns:
        ImageSize mit Pixel-Dimensionen
    """
    width, height = label.get_size_dots(dpi)
    return ImageSize(
        width=width,
        height=height,
        dpi=dpi,
        label=label
    )
