"""
Drucker-Registry: Mapping von USB VID:PID zu Drucker-Klassen.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Type, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .printer import Printer


@dataclass
class PrinterRegistration:
    """Registrierungsdaten für einen Drucker-Typ."""
    printer_class: Type["Printer"]
    usb_vid: int
    usb_pid: int
    name: str
    manufacturer: str
    model: Optional[str] = None  # Spezifisches Modell (z.B. "M120", "M221")
    probe: Optional[Callable[[str], Dict[str, Any]]] = None  # Optionaler Probe-Hook
    # Datenblatt-Felder (aus Klassenkonstanten, kein Live-Query)
    max_width_mm: Optional[float] = None
    dpi: Optional[int] = None
    supported_paper_types: Optional[List[str]] = None  # Liste der Enum-Namen
    supported_densities: Optional[List[str]] = None
    supported_print_technologies: Optional[List[str]] = None  # Z.B. ["DIRECT_THERMAL", "THERMAL_TRANSFER"]
    print_technology: Optional[str] = None  # Aktuell eingestelltes Verfahren (z.B. "THERMAL_TRANSFER")


# Globale Registry
_registry: Dict[tuple, PrinterRegistration] = {}
_model_registry: Dict[str, PrinterRegistration] = {}  # Modell -> Registration


def register_printer(
    usb_vid: int,
    usb_pid: int,
    name: str,
    manufacturer: str = "Unknown",
    model: Optional[str] = None,
    probe: Optional[Callable[[str], Dict[str, Any]]] = None,
):
    """Decorator zum Registrieren einer Drucker-Klasse.
    
    Datenblatt-Felder (max_width_mm, dpi, paper_types, densities) werden
    automatisch aus den Klassenkonstanten der Printer-Subklasse gelesen,
    sofern sie vorhanden sind.
    
    Usage:
        @register_printer(usb_vid=0x0483, usb_pid=0x5740, name="Phomemo M221", model="M221")
        class PhomemoM221(Printer):
            ...
    """
    def decorator(cls: Type["Printer"]) -> Type["Printer"]:
        # Datenblatt-Werte automatisch aus Klassenkonstanten lesen
        pt = getattr(cls, '_SUPPORTED_PAPER_TYPES', None)
        ds = getattr(cls, '_SUPPORTED_DENSITIES', None)
        techs = getattr(cls, '_SUPPORTED_PRINT_TECHNOLOGIES', None)
        # _PRINT_TECHNOLOGY kann Enum oder String sein
        current_tech = getattr(cls, '_PRINT_TECHNOLOGY', None)
        if current_tech is not None:
            if hasattr(current_tech, 'name'):
                current_tech_str = current_tech.name
            else:
                current_tech_str = str(current_tech)
        else:
            current_tech_str = None
        reg = PrinterRegistration(
            printer_class=cls,
            usb_vid=usb_vid,
            usb_pid=usb_pid,
            name=name,
            manufacturer=manufacturer,
            model=model,
            probe=probe,
            max_width_mm=getattr(cls, '_MAX_WIDTH_MM', None),
            dpi=getattr(cls, '_DPI', None),
            supported_paper_types=[t.name for t in pt] if pt else None,
            supported_densities=[d.name for d in ds] if ds else None,
            supported_print_technologies=[t.name for t in techs] if techs else None,
            print_technology=current_tech_str,
        )
        
        key = (usb_vid, usb_pid)
        # Nur als Default registrieren wenn kein Model angegeben
        # oder wenn noch kein Default existiert
        if model is None or key not in _registry:
            _registry[key] = reg
        
        # Modell-spezifische Registry
        if model:
            _model_registry[model.upper()] = reg
        
        return cls
    return decorator


def get_printer_class(usb_vid: int, usb_pid: int) -> Optional[Type["Printer"]]:
    """Finde Drucker-Klasse für USB VID:PID.
    
    Returns:
        Printer-Klasse oder None wenn nicht registriert.
    """
    key = (usb_vid, usb_pid)
    reg = _registry.get(key)
    return reg.printer_class if reg else None


def get_registration(usb_vid: int, usb_pid: int) -> Optional[PrinterRegistration]:
    """Hole Registrierungsdaten für USB VID:PID."""
    return _registry.get((usb_vid, usb_pid))


def get_registration_by_model(model: str) -> Optional[PrinterRegistration]:
    """Hole Registrierungsdaten für ein spezifisches Modell."""
    return _model_registry.get(model.upper())


def get_all_registrations() -> List[PrinterRegistration]:
    """Liste aller registrierten Drucker."""
    return list(_registry.values())


def is_supported(usb_vid: int, usb_pid: int) -> bool:
    """Prüfe ob USB-Gerät ein unterstützter Drucker ist."""
    return (usb_vid, usb_pid) in _registry
