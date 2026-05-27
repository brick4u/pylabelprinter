"""
Drucker-Discovery: Finden von angeschlossenen Druckern.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Type, Dict

from .registry import get_registration, get_registration_by_model, PrinterRegistration


@dataclass
class PrinterDevice:
    """Gefundenes Drucker-Gerät."""
    device_id: str          # z.B. "usb:0483:5740:/dev/usb/lp0"
    device_path: str        # z.B. "/dev/usb/lp0"
    name: str               # z.B. "Phomemo M221"
    manufacturer: str       # z.B. "Phomemo"
    model: str              # z.B. "M221" (aus IEEE 1284 ID)
    usb_vid: int
    usb_pid: int
    registration: Optional[PrinterRegistration]
    usb_port: Optional[str] = None     # z.B. "3-1.4.4" (stabiler USB-Port-Pfad)
    ieee1284_id: Optional[str] = None  # Raw IEEE 1284 ID String
    serial_number: Optional[str] = None  # Seriennummer (falls abfragbar)
    
    def __str__(self) -> str:
        return f"{self.device_id}  {self.name}"


def _parse_ieee1284_id(ieee1284_str: str) -> Dict[str, str]:
    """Parse IEEE 1284 ID String in ein Dictionary.
    
    Beispiel: "MFG:Phomemo;CMD:XPP,XL;MDL:M120;CLS:PRINTER;DES:LABEL PRINTER;"
    Ergibt: {"MFG": "Phomemo", "CMD": "XPP,XL", "MDL": "M120", ...}
    """
    result = {}
    # Format: KEY:VALUE; oder KEY:VALUE
    parts = ieee1284_str.strip().rstrip(";").split(";")
    for part in parts:
        if ":" in part:
            key, _, value = part.partition(":")
            result[key.strip().upper()] = value.strip()
    return result


def _read_ieee1284_id(device_path: str) -> Optional[str]:
    """Lese IEEE 1284 Device ID für ein USB-Drucker-Gerät.
    
    Die IEEE 1284 ID enthält Hersteller, Modell und andere Infos.
    Beispiel: "MFG:;CMD:XPP,XL;MDL:M120;CLS:PRINTER;DES:LABEL PRINTER;"
    """
    try:
        device_name = os.path.basename(device_path)
        
        # Versuche verschiedene sysfs-Pfade
        sysfs_paths = [
            Path(f"/sys/class/usbmisc/{device_name}/device/ieee1284_id"),
            Path(f"/sys/class/usb/{device_name}/device/ieee1284_id"),
        ]
        
        for path in sysfs_paths:
            if path.exists():
                return path.read_text().strip()
    except (OSError, IOError):
        pass
    
    return None


def _read_usb_port(device_path: str) -> Optional[str]:
    """Lese den stabilen USB-Port-Pfad für ein Gerät.
    
    Der Port-Pfad (z.B. "3-1.4.4") ist stabil und ändert sich nicht,
    solange das Gerät am selben physischen USB-Port bleibt.
    
    Format: Bus-Port[.HubPort[.HubPort...]]
    """
    try:
        device_name = os.path.basename(device_path)
        
        sysfs_paths = [
            Path(f"/sys/class/usbmisc/{device_name}/device"),
            Path(f"/sys/class/usb/{device_name}/device"),
        ]
        
        for sysfs_path in sysfs_paths:
            if sysfs_path.exists():
                # Auflösen zu absolutem Pfad
                real_path = str(sysfs_path.resolve())
                # Extrahiere Port-Pfad (z.B. "3-1.4.4" aus "...usb3/3-1/3-1.4/3-1.4.4/3-1.4.4:1.0")
                # Letztes Segment vor dem Interface-Teil (:X.Y)
                match = re.search(r'/(\d+-[\d.]+):\d+\.\d+$', real_path)
                if match:
                    return match.group(1)
    except (OSError, IOError):
        pass
    
    return None


def _parse_usb_ids(device_path: str) -> Optional[tuple]:
    """Lese USB VID:PID für ein /dev/usb/lpX Gerät."""
    # Finde das zugehörige USB-Gerät via sysfs
    try:
        # /dev/usb/lp0 -> /sys/class/usbmisc/lp0/device
        device_name = os.path.basename(device_path)
        sysfs_path = Path(f"/sys/class/usbmisc/{device_name}/device")
        
        if not sysfs_path.exists():
            # Fallback: /sys/class/usb/lp0/device
            sysfs_path = Path(f"/sys/class/usb/{device_name}/device")
        
        if not sysfs_path.exists():
            return None
        
        # Gehe zum USB-Gerät hoch
        usb_device = sysfs_path.resolve().parent
        
        vid_path = usb_device / "idVendor"
        pid_path = usb_device / "idProduct"
        
        if vid_path.exists() and pid_path.exists():
            vid = int(vid_path.read_text().strip(), 16)
            pid = int(pid_path.read_text().strip(), 16)
            return (vid, pid)
    except (OSError, ValueError):
        pass
    
    return None


def list_printers() -> List[PrinterDevice]:
    """Liste alle angeschlossenen und unterstützten Drucker.
    
    Scannt /dev/usb/lp* nach USB-Druckern und prüft gegen Registry.
    Das Modell wird aus der IEEE 1284 ID gelesen (MDL-Feld).
    
    Returns:
        Liste von PrinterDevice-Objekten.
    """
    devices = []
    
    # Scanne USB-Drucker
    usb_dev_path = Path("/dev/usb")
    if usb_dev_path.exists():
        for lp_path in sorted(usb_dev_path.glob("lp*")):
            device_path = str(lp_path)
            usb_ids = _parse_usb_ids(device_path)
            
            if usb_ids:
                vid, pid = usb_ids
                reg = get_registration(vid, pid)
                
                if reg:
                    # IEEE 1284 ID für genaue Modell-Erkennung lesen
                    ieee1284_str = _read_ieee1284_id(device_path)
                    ieee1284 = _parse_ieee1284_id(ieee1284_str) if ieee1284_str else {}
                
                    # Modell aus IEEE 1284 ID (MDL-Feld)
                    model = ieee1284.get("MDL", "")
                
                    # Falls Modell registriert ist, bevorzugen
                    if model:
                        model_reg = get_registration_by_model(model)
                        if model_reg:
                            reg = model_reg
                
                    # USB-Port-Pfad (stabil)
                    usb_port = _read_usb_port(device_path)
                
                    # Name: Verwende Modell aus IEEE 1284 wenn vorhanden
                    if model:
                        name = f"{reg.manufacturer} {model}"
                    else:
                        name = reg.name
                
                    # Optionale Treiber-spezifische Probe (z.B. Seriennummer)
                    serial_number = None
                    if reg.probe:
                        try:
                            probe_data = reg.probe(device_path)
                            serial_number = probe_data.get("serial_number")
                        except Exception:
                            serial_number = None
                    
                    device_id = f"usb:{vid:04x}:{pid:04x}:{device_path}"
                    devices.append(PrinterDevice(
                        device_id=device_id,
                        device_path=device_path,
                        name=name,
                        manufacturer=reg.manufacturer,
                        model=model,
                        usb_vid=vid,
                        usb_pid=pid,
                        registration=reg,
                        usb_port=usb_port,
                        ieee1284_id=ieee1284_str,
                        serial_number=serial_number,
                    ))
    
    return devices


def find_printer(device_id: Optional[str] = None, model: Optional[str] = None, usb_port: Optional[str] = None, serial: Optional[str] = None) -> Optional[PrinterDevice]:
    """Finde einen spezifischen Drucker oder den ersten verfügbaren.
    
    Args:
        device_id: Optionale Device-ID oder Pfad. 
        model: Optionaler Modellname (z.B. "M120", "M221").
        usb_port: Optionaler USB-Port-Pfad (z.B. "3-1.4.4").
        serial: Optionale Seriennummer (z.B. "Q218G4C48320027").
               Wenn alle None, wird der erste gefundene zurückgegeben.
        
    Returns:
        PrinterDevice oder None.
    """
    printers = list_printers()
    
    if not printers:
        return None
    
    # Nach Seriennummer suchen
    if serial:
        serial_upper = serial.upper()
        for printer in printers:
            if printer.serial_number and printer.serial_number.upper() == serial_upper:
                return printer
        return None
    
    # Nach USB-Port suchen
    if usb_port:
        for printer in printers:
            if printer.usb_port == usb_port:
                return printer
        return None
    
    # Nach Modell suchen
    if model:
        model_upper = model.upper()
        for printer in printers:
            if printer.model.upper() == model_upper:
                return printer
        return None
    
    # Nach Device-ID oder Pfad suchen
    if device_id is None:
        return printers[0]
    
    for printer in printers:
        if printer.device_id == device_id or printer.device_path == device_id:
            return printer
    
    return None
