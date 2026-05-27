#!/usr/bin/env python3
"""
pylabelprinter CLI - Label Printer Command Line Interface

Verwendung:
    pylabelprinter list              - Liste alle Drucker
    pylabelprinter info              - Zeige Drucker-Info
    pylabelprinter label-size WxH    - Zeige Bildgröße für Label
    pylabelprinter print IMAGE       - Drucke Bild
    pylabelprinter render-template   - Rendere YAML-Template als Bild
"""

import argparse
import sys
from pathlib import Path

# Füge src-Verzeichnis zum Python-Path hinzu für direktes Ausführen
sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_list(args):
    """Liste alle verfügbaren Drucker."""
    import pylabelprinter
    
    printers = pylabelprinter.list_printers()
    
    if not printers:
        print("Keine unterstützten Drucker gefunden.")
        return 1
    
    print(f"Gefundene Drucker ({len(printers)}):")
    for p in printers:
        print(f"  {p.device_id}")
        print(f"    Name:     {p.name}")
        print(f"    Modell:   {p.model}")
        if p.serial_number:
            print(f"    Serial:   {p.serial_number}")
        print(f"    Pfad:     {p.device_path}")
        if p.usb_port:
            print(f"    USB-Port: {p.usb_port}")
    
    return 0


def cmd_info(args):
    """Zeige Drucker-Informationen."""
    import pylabelprinter
    
    try:
        # Erst Discovery-Daten holen
        device = pylabelprinter.find_printer(
            args.device, 
            model=args.model, 
            usb_port=args.usb_port, 
            serial=args.serial
        )
        
        if device is None:
            print("Fehler: Kein Drucker gefunden", file=sys.stderr)
            return 1
        
        # Discovery-Daten anzeigen
        print(f"Drucker: {device.name}")
        print(f"  Device-ID:  {device.device_id}")
        print(f"  Modell:     {device.model}")
        if device.serial_number:
            print(f"  Serial:     {device.serial_number}")
        print(f"  Pfad:       {device.device_path}")
        if device.usb_port:
            print(f"  USB-Port:   {device.usb_port}")
        
        # Abgefragte Daten vom Drucker
        print()
        print("Status (abgefragt):")
        
        with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
            info = printer.get_info()
            
            print(f"  Firmware:     {info.firmware_version}")
            print(f"  Seriennummer: {info.serial_number}")
            print(f"  Max. Breite:  {info.max_width_mm}mm")
            print(f"  Auflösung:    {info.dpi} DPI")
            
            if info.battery_level is not None:
                print(f"  Akku:         {info.battery_level}%")
            
            if info.has_paper is not None:
                status = "Ja" if info.has_paper else "Nein"
                print(f"  Papier:       {status}")
            
            if info.paper_type is not None:
                print(f"  Papierart:    {info.paper_type.name}")
            
            if info.auto_off_time is not None:
                print(f"  Auto-Off:     {info.auto_off_time.name}")
            
            if info.supported_paper_types:
                types = ", ".join(t.name for t in info.supported_paper_types)
                print(f"  Papierarten:  {types}")
    
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PermissionDeniedError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterConnectionError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_label_size(args):
    """Zeige Bildgröße für ein Label."""
    import pylabelprinter
    
    # Parse WxH Format
    try:
        width, height = args.size.lower().split("x")
        width = float(width)
        height = float(height)
    except ValueError:
        print(f"Fehler: Ungültiges Format '{args.size}'. Verwende WxH (z.B. 40x30)", file=sys.stderr)
        return 1
    
    label = pylabelprinter.Label(width, height)
    size = pylabelprinter.get_image_size(label, dpi=args.dpi)
    
    print(f"Label: {label}")
    print(f"  Auflösung:    {size.dpi} DPI")
    print(f"  Bildgröße:    {size.width} x {size.height} Pixel")
    print(f"  Bytes (raw):  {size.bytes_uncompressed}")
    
    return 0


def cmd_test(args):
    """Drucke ein Testbild."""
    import pylabelprinter
    
    # Label-Größe parsen
    try:
        width, height = args.label.lower().split("x")
        label = pylabelprinter.Label(float(width), float(height))
    except ValueError:
        print(f"Fehler: Ungültiges Label-Format '{args.label}'", file=sys.stderr)
        return 1
    
    try:
        with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
            print(f"Drucke Testbild auf {label}...")
            pylabelprinter.print_test_label(
                printer,
                label,
                copies=args.copies,
                density=args.density,
            )
            print("Fertig!")
    
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Fehler: Kein Papier eingelegt!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    
    return 0


def _parse_paper_type(paper_type_str: str):
    """Parse Papierart-String zu PaperType Enum."""
    import pylabelprinter
    
    if not paper_type_str:
        return None
    
    try:
        return pylabelprinter.PaperType[paper_type_str.upper()]
    except KeyError:
        valid = ", ".join(t.name for t in pylabelprinter.PaperType)
        raise ValueError(f"Ungültige Papierart '{paper_type_str}'. Gültig: {valid}")


def _get_dpi_from_model_or_device(args) -> int:
    """Ermittle DPI aus dem Druckermodell (Registry/Discovery)."""
    import pylabelprinter
    from pylabelprinter.registry import get_registration_by_model

    # 1) Explizites Modell
    if args.model:
        reg = get_registration_by_model(args.model)
        if reg and hasattr(reg.printer_class, "_DPI"):
            return int(reg.printer_class._DPI)

    # 2) Gerät/USB-Port/Serial via Discovery
    device = pylabelprinter.find_printer(
        args.device,
        model=args.model,
        usb_port=args.usb_port,
        serial=args.serial,
    )
    if device and device.registration and hasattr(device.registration.printer_class, "_DPI"):
        return int(device.registration.printer_class._DPI)

    raise ValueError(
        "Konnte DPI nicht aus dem Modell bestimmen. "
        "Bitte --model oder ein konkretes Gerät angeben (--device/--usb-port/--serial)."
    )


def _do_print(args, image, label):
    """Gemeinsame Drucklogik für print und print-template."""
    import pylabelprinter
    
    # Paper Type
    paper_type = None
    if hasattr(args, 'paper_type') and args.paper_type:
        paper_type = _parse_paper_type(args.paper_type)
    
    # Density
    density = getattr(args, 'density', 10)
    copies = getattr(args, 'copies', 1)
    
    with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
        if paper_type:
            printer.paper_type = paper_type
        
        printer.print_image(
            image, 
            label, 
            copies=copies,
            density=density,
        )


def cmd_print_template(args):
    """Drucke ein YAML-Template."""
    import pylabelprinter
    
    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Fehler: Template nicht gefunden: {template_path}", file=sys.stderr)
        return 1
    
    # Variablen parsen (key=value)
    variables = {}
    if args.var:
        for var in args.var:
            if "=" in var:
                key, _, value = var.partition("=")
                variables[key.strip()] = value.strip()
            else:
                print(f"Warnung: Ungültige Variable '{var}', erwarte key=value", file=sys.stderr)

    try:
        template = pylabelprinter.LabelTemplate.from_file(template_path, variables=variables)
    except Exception as e:
        print(f"Fehler beim Laden des Templates: {e}", file=sys.stderr)
        return 1
    
    try:
        # Render Template zu Bild
        image = pylabelprinter.render_template(template)
        label = pylabelprinter.Label(template.width_mm, template.height_mm)
        
        print(f"Drucke Template {template_path} ({template.width_mm}x{template.height_mm}mm)...")
        if variables:
            print(f"  Variablen: {variables}")
        
        _do_print(args, image, label)
        print("Fertig!")
    
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Fehler: Kein Papier eingelegt!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_render_template(args):
    """Rendere ein YAML-Template als Bilddatei."""
    import pylabelprinter

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Fehler: Template nicht gefunden: {template_path}", file=sys.stderr)
        return 1

    # Variablen parsen (key=value)
    variables = {}
    if args.var:
        for var in args.var:
            if "=" in var:
                key, _, value = var.partition("=")
                variables[key.strip()] = value.strip()
            else:
                print(f"Warnung: Ungültige Variable '{var}', erwarte key=value", file=sys.stderr)

    try:
        dpi = _get_dpi_from_model_or_device(args)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1

    try:
        template = pylabelprinter.LabelTemplate.from_file(template_path, variables=variables)
        image = pylabelprinter.render_template(template, dpi=dpi)
    except Exception as e:
        print(f"Fehler beim Rendern des Templates: {e}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    try:
        image.save(output_path)
    except Exception as e:
        print(f"Fehler beim Speichern: {e}", file=sys.stderr)
        return 1

    print(f"Gerendert: {template_path} -> {output_path} ({dpi} DPI)")
    return 0


def cmd_print(args):
    """Drucke ein Bild."""
    import pylabelprinter
    from PIL import Image
    
    # Bild laden
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Fehler: Datei nicht gefunden: {image_path}", file=sys.stderr)
        return 1
    
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Fehler beim Laden: {e}", file=sys.stderr)
        return 1
    
    # Label-Größe parsen
    try:
        width, height = args.label.lower().split("x")
        label = pylabelprinter.Label(float(width), float(height))
    except ValueError:
        print(f"Fehler: Ungültiges Label-Format '{args.label}'", file=sys.stderr)
        return 1
    
    try:
        print(f"Drucke {image_path} auf {label}...")
        _do_print(args, image, label)
        print("Fertig!")
    
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Fehler: Kein Papier eingelegt!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="pylabelprinter",
        description="Label Printer CLI"
    )
    parser.add_argument("--device", "-d", help="Device-ID oder Pfad (z.B. /dev/usb/lp0)")
    parser.add_argument("--model", "-m", help="Modellname (z.B. M120, M221)")
    parser.add_argument("--usb-port", "-u", help="USB-Port-Pfad (z.B. 3-1.4.4)")
    parser.add_argument("--serial", "-s", help="Seriennummer (z.B. Q218G4C48320027)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # list
    subparsers.add_parser("list", help="Liste alle Drucker")
    
    # info
    subparsers.add_parser("info", help="Zeige Drucker-Info")
    
    # label-size
    p_size = subparsers.add_parser("label-size", help="Zeige Bildgröße für Label")
    p_size.add_argument("size", help="Label-Größe (z.B. 40x30)")
    p_size.add_argument("--dpi", type=int, default=203, help="DPI (Standard: 203)")
    
    # print
    p_print = subparsers.add_parser("print", help="Drucke Bild")
    p_print.add_argument("image", help="Bild-Datei")
    p_print.add_argument("--label", "-l", required=True, help="Label-Größe (z.B. 40x30)")
    p_print.add_argument("--copies", "-c", type=int, default=1, help="Anzahl Kopien")
    p_print.add_argument("--density", type=int, default=10, help="Druckdichte (1-15)")
    p_print.add_argument("--paper-type", "-p", help="Papierart (GAP, CONTINUOUS, BLACK_MARK)")
    
    # print-template
    p_template = subparsers.add_parser("print-template", help="Drucke YAML-Template")
    p_template.add_argument("template", help="YAML-Template-Datei")
    p_template.add_argument("--var", "-v", action="append", help="Variable (key=value), mehrfach möglich")
    p_template.add_argument("--copies", "-c", type=int, default=1, help="Anzahl Kopien")
    p_template.add_argument("--density", type=int, default=10, help="Druckdichte (1-15)")
    p_template.add_argument("--paper-type", "-p", help="Papierart (GAP, CONTINUOUS, BLACK_MARK)")

    # render-template
    p_render = subparsers.add_parser("render-template", help="Rendere YAML-Template als Bild")
    p_render.add_argument("template", help="YAML-Template-Datei")
    p_render.add_argument("output", help="Ausgabe-Bilddatei (z.B. out.png)")
    p_render.add_argument("--var", "-v", action="append", help="Variable (key=value), mehrfach möglich")
    
    # test
    p_test = subparsers.add_parser("test", help="Drucke Testbild")
    p_test.add_argument("--label", "-l", required=True, help="Label-Größe (z.B. 40x30)")
    p_test.add_argument("--copies", "-c", type=int, default=1, help="Anzahl Kopien")
    p_test.add_argument("--density", type=int, default=10, help="Druckdichte (1-15)")
    
    args = parser.parse_args()
    
    if args.command == "list":
        return cmd_list(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "label-size":
        return cmd_label_size(args)
    elif args.command == "print":
        return cmd_print(args)
    elif args.command == "print-template":
        return cmd_print_template(args)
    elif args.command == "render-template":
        return cmd_render_template(args)
    elif args.command == "test":
        return cmd_test(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
