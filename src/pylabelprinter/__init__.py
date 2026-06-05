"""
pylabelprinter - Python Label Printer Library

Eine generische Python-Bibliothek für Label-Drucker.

Beispiel:
    import pylabelprinter
    
    # Drucker auflisten
    printers = pylabelprinter.list_printers()
    
    # Drucker öffnen
    with pylabelprinter.open() as printer:
        info = printer.get_info()
        print(f"Drucker: {info.model}, FW: {info.firmware_version}")
        
        # Drucken
        from PIL import Image
        image = Image.open("label.png")
        printer.print_image(image, pylabelprinter.Label(40, 30))
"""

from typing import Optional, List

from .label import Label, ImageSize, get_image_size
from .enums import PaperType, Alignment, AutoOffTime, PrintDensity, PrintTechnology
from .testlabel import create_test_label, print_test_label
from .template import LabelTemplate, render_template, print_template
from .exceptions import (
    LabelprinterError,
    PrinterNotFoundError,
    PrinterConnectionError,
    PermissionDeniedError,
    PrinterStandbyError,
    UnsupportedFeatureError,
    PrintError,
    NoPaperError,
)
from .printer import Printer, PrinterInfo
from .discovery import list_printers, find_printer, PrinterDevice
from .connection import Connection, UsbConnection

# Importiere Drucker-Treiber (registrieren sich automatisch)
from .printers import phomemo  # noqa: F401
from .printers import zebra  # noqa: F401


__version__ = "0.1.0"
__all__ = [
    # High-Level API
    "list_printers",
    "open",
    "get_image_size",
    "create_test_label",
    "print_test_label",
    "render_template",
    "print_template",
    # Classes
    "Printer",
    "PrinterInfo",
    "PrinterDevice",
    "Label",
    "ImageSize",
    "LabelTemplate",
    "Connection",
    "UsbConnection",
    # Enums
    "PaperType",
    "Alignment",
    "AutoOffTime",
    "PrintDensity",
    "PrintTechnology",
    # Exceptions
    "LabelprinterError",
    "PrinterNotFoundError",
    "PrinterConnectionError",
    "UnsupportedFeatureError",
    "PrintError",
    "NoPaperError",
]


def open(device_id: Optional[str] = None, model: Optional[str] = None, usb_port: Optional[str] = None, serial: Optional[str] = None) -> Printer:
    """Öffne einen Label-Drucker.
    
    Args:
        device_id: Optionale Device-ID oder Pfad.
                   Wenn None, wird der erste gefundene Drucker verwendet.
        model: Optionaler Modellname (z.B. "M120", "M221").
        usb_port: Optionaler USB-Port-Pfad (z.B. "3-1.4.4").
        serial: Optionale Seriennummer (z.B. "Q218G4C48320027").
    
    Returns:
        Printer-Instanz (noch nicht verbunden, use connect() oder with-Statement)
        
    Raises:
        PrinterNotFoundError: Kein passender Drucker gefunden.
        
    Beispiel:
        # Automatisch ersten Drucker nehmen
        printer = pylabelprinter.open()
        printer.connect()
        
        # Oder mit with-Statement
        with pylabelprinter.open() as printer:
            printer.print_image(image, Label(40, 30))
            
        # Spezifischen Drucker nach Pfad
        printer = pylabelprinter.open("/dev/usb/lp0")
        
        # Spezifischen Drucker nach Modell
        printer = pylabelprinter.open(model="M221")
        
        # Spezifischen Drucker nach USB-Port
        printer = pylabelprinter.open(usb_port="3-1.4.4")
        
        # Spezifischen Drucker nach Seriennummer
        printer = pylabelprinter.open(serial="Q218G4C48320027")
    """
    device = find_printer(device_id, model=model, usb_port=usb_port, serial=serial)
    
    if device is None:
        if serial:
            raise PrinterNotFoundError(f"No printer with serial '{serial}' found")
        elif usb_port:
            raise PrinterNotFoundError(f"No printer at USB port '{usb_port}' found")
        elif model:
            raise PrinterNotFoundError(f"No printer with model '{model}' found")
        elif device_id:
            raise PrinterNotFoundError(f"No printer found at {device_id}")
        else:
            raise PrinterNotFoundError("No supported printer found")
    
    if device.registration is None:
        raise PrinterNotFoundError(f"No driver for device {device.device_id}")
    
    # Versuche modell-spezifischen Treiber zu finden
    from .registry import get_registration_by_model
    
    if device.model:
        model_reg = get_registration_by_model(device.model)
        if model_reg:
            printer_class = model_reg.printer_class
        else:
            # Fallback auf VID:PID-basierte Registration
            printer_class = device.registration.printer_class
    else:
        printer_class = device.registration.printer_class
    
    # Erstelle Connection und Printer
    connection = UsbConnection(
        device.device_path,
        write_chunk_size=getattr(printer_class, "_USB_WRITE_CHUNK_SIZE", None),
        write_chunk_delay=getattr(printer_class, "_USB_WRITE_CHUNK_DELAY", None),
        write_retry_delay=getattr(printer_class, "_USB_WRITE_RETRY_DELAY", None),
    )
    
    return printer_class(connection)
