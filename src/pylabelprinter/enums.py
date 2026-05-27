"""
Generische Enums für pylabelprinter - treiberunabhängig.
"""

from enum import Enum, auto


class PaperType(Enum):
    """Papierarten für Label-Drucker."""
    CONTINUOUS = auto()    # Endlospapier (keine Erkennung)
    GAP = auto()           # Etiketten mit Lücke (Transparenz-Sensor)
    BLACK_MARK = auto()    # Schwarze Markierung auf Rückseite
    HOLE = auto()          # Lochung


class Alignment(Enum):
    """Bild-Ausrichtung auf Label."""
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()


class AutoOffTime(Enum):
    """Auto-Abschaltzeit."""
    OFF = 0           # Nie abschalten
    MIN_1 = 1         # 1 Minute
    MIN_5 = 5         # 5 Minuten  
    MIN_10 = 10       # 10 Minuten
    MIN_15 = 15       # 15 Minuten
    MIN_20 = 20       # 20 Minuten
    MIN_30 = 30       # 30 Minuten
    MIN_60 = 60       # 60 Minuten
    MIN_120 = 120     # 120 Minuten


class PrintDensity(Enum):
    """Druckdichte/Schwärze.
    
    Steuert die Hitze des Thermodruckkopfs:
    - LIGHT: Weniger Hitze, hellerer Druck (für empfindliches Papier)
    - MEDIUM: Standard-Hitze, normaler Druck
    - DARK: Mehr Hitze, dunklerer/kräftigerer Druck
    """
    LIGHT = auto()        # Fein - weniger Hitze
    MEDIUM_LIGHT = auto() # Leicht
    MEDIUM = auto()       # Standard
    MEDIUM_DARK = auto()  # Kräftig
    DARK = auto()         # Dick - mehr Hitze
