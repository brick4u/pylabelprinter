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
    
    Usage:
        @register_printer(usb_vid=0x0483, usb_pid=0x5740, name="Phomemo M221", model="M221")
        class PhomemoM221(Printer):
            ...
    """
    def decorator(cls: Type["Printer"]) -> Type["Printer"]:
        reg = PrinterRegistration(
            printer_class=cls,
            usb_vid=usb_vid,
            usb_pid=usb_pid,
            name=name,
            manufacturer=manufacturer,
            model=model,
            probe=probe,
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
