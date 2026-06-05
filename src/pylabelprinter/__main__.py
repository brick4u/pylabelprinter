#!/usr/bin/env python3
"""
pylabelprinter CLI - Label Printer Command Line Interface

Usage:
    pylabelprinter list              - List all printers
    pylabelprinter info              - Show printer information
    pylabelprinter label-size WxH    - Show image size for a label
    pylabelprinter print IMAGE       - Print an image
    pylabelprinter render-template   - Render a YAML template as an image
"""

import argparse
import sys
from pathlib import Path

# Add src directory to Python path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_list(args):
    """List all available printers."""
    import pylabelprinter
    
    printers = pylabelprinter.list_printers()
    
    if not printers:
        print("No supported printers found.")
        return 1
    
    print(f"Found {len(printers)} printer(s):")
    for p in printers:
        print(f"  {p.device_id}")
        print(f"    Name:         {p.name}")
        print(f"    Model:        {p.model}")
        if p.serial_number:
            print(f"    Serial:       {p.serial_number}")
        print(f"    Manufacturer: {p.manufacturer}")
        print(f"    Path:         {p.device_path}")
        if p.usb_port:
            print(f"    USB Port:     {p.usb_port}")
        if p.max_width_mm is not None:
            print(f"    Width:        {p.max_width_mm}mm")
        if p.dpi is not None:
            print(f"    Resolution:   {p.dpi} DPI")
        if p.supported_paper_types:
            print(f"    Paper Types:  {', '.join(p.supported_paper_types)}")
        if p.supported_densities:
            print(f"    Densities:    {', '.join(p.supported_densities)}")
        if p.supported_print_technologies:
            print(f"    Print Techs:  {', '.join(t.replace('_', ' ').title() for t in p.supported_print_technologies)}")
        if p.print_technology:
            print(f"    Print Tech:   {p.print_technology.replace('_', ' ').title()}")
    
    return 0


def cmd_info(args):
    """Show printer information."""
    import pylabelprinter
    
    try:
        # First get discovery data
        device = pylabelprinter.find_printer(
            args.device, 
            model=args.model, 
            usb_port=args.usb_port, 
            serial=args.serial
        )
        
        if device is None:
            print("Error: No printer found", file=sys.stderr)
            return 1
        
        print(f"Printer: {device.name}")
        print()
        print("Model / Driver Data:")
        print(f"  Device-ID:    {device.device_id}")
        print(f"  Model:        {device.model}")
        if device.serial_number:
            print(f"  Serial:       {device.serial_number}")
        print(f"  Manufacturer: {device.manufacturer}")
        print(f"  Path:         {device.device_path}")
        if device.usb_port:
            print(f"  USB Port:     {device.usb_port}")
        if device.max_width_mm is not None:
            print(f"  Width:        {device.max_width_mm}mm")
        if device.dpi is not None:
            print(f"  Resolution:   {device.dpi} DPI")
        if device.supported_paper_types:
            print(f"  Paper Types:  {', '.join(device.supported_paper_types)}")
        if device.supported_densities:
            print(f"  Densities:    {', '.join(device.supported_densities)}")
        if device.supported_print_technologies:
            print(f"  Print Techs:  {', '.join(t.replace('_', ' ').title() for t in device.supported_print_technologies)}")
        
        print()
        print("Live Status (queried):")
        
        with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
            info = printer.get_info()
            
            print(f"  Firmware:   {info.firmware_version}")
            print(f"  Serial:     {info.serial_number}")
            if info.battery_level is not None:
                print(f"  Battery:    {info.battery_level}%")
            if info.has_paper is not None:
                status = "Yes" if info.has_paper else "No"
                print(f"  Paper:      {status}")
            if info.paper_type is not None:
                print(f"  Paper Type: {info.paper_type.name}")
            if info.auto_off_time is not None:
                print(f"  Auto Off:   {info.auto_off_time.name}")
            if info.print_density is not None:
                print(f"  Density:    {info.print_density.name}")
            if info.print_technology is not None:
                print(f"  Print Tech: {info.print_technology.name.replace('_', ' ').title()}")
    
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PermissionDeniedError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_label_size(args):
    """Show image size for a label."""
    import pylabelprinter
    
    # Parse WxH Format
    try:
        width, height = args.size.lower().split("x")
        width = float(width)
        height = float(height)
    except ValueError:
        print(f"Error: Invalid format '{args.size}'. Use WxH (e.g. 40x30)", file=sys.stderr)
        return 1
    
    label = pylabelprinter.Label(width, height)
    size = pylabelprinter.get_image_size(label, dpi=args.dpi)
    
    print(f"Label: {label}")
    print(f"  Resolution: {size.dpi} DPI")
    print(f"  Image Size: {size.width} x {size.height} px")
    print(f"  Raw Bytes:  {size.bytes_uncompressed}")
    
    return 0


def cmd_test(args):
    """Print a test image."""
    import pylabelprinter
    
    # Parse label dimensions
    try:
        width, height = args.label.lower().split("x")
        label = pylabelprinter.Label(float(width), float(height))
    except ValueError:
        print(f"Error: Invalid label format '{args.label}'.", file=sys.stderr)
        return 1
    
    try:
        x_off = getattr(args, 'x_offset', 0.0) or 0.0
        y_off = getattr(args, 'y_offset', 0.0) or 0.0
        with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
            _configure_printer_for_job(printer, args)
            print(f"Printing test label on {label}...")
            pylabelprinter.print_test_label(
                printer,
                label,
                copies=args.copies,
                density=args.density,
                x_offset_mm=x_off,
                y_offset_mm=y_off,
            )
            print("Done!")
    
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Error: No paper loaded!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def _parse_paper_type(paper_type_str: str):
    """Parse paper type string to PaperType enum."""
    import pylabelprinter
    
    if not paper_type_str:
        return None
    
    try:
        return pylabelprinter.PaperType[paper_type_str.upper()]
    except KeyError:
        valid = ", ".join(t.name for t in pylabelprinter.PaperType)
        raise ValueError(f"Invalid paper type '{paper_type_str}'. Valid: {valid}")


def _parse_print_technology(print_technology_str: str):
    """Parse print technology string to PrintTechnology enum."""
    import pylabelprinter

    if not print_technology_str:
        return None

    normalized = print_technology_str.strip().replace("-", "_").replace(" ", "_").upper()
    aliases = {
        "THERMALTRANSFER": "THERMAL_TRANSFER",
        "THERMAL_TRANSFER": "THERMAL_TRANSFER",
        "TRANSFER": "THERMAL_TRANSFER",
        "DIRECTTHERMAL": "DIRECT_THERMAL",
        "DIRECT_THERMAL": "DIRECT_THERMAL",
        "DIRECT": "DIRECT_THERMAL",
    }
    normalized = aliases.get(normalized, normalized)

    try:
        return pylabelprinter.PrintTechnology[normalized]
    except KeyError:
        valid = ", ".join(t.name for t in pylabelprinter.PrintTechnology)
        raise ValueError(
            f"Invalid print technology '{print_technology_str}'. Valid: {valid}"
        )


def _configure_printer_for_job(printer, args) -> None:
    """Apply optional printer settings before printing."""
    paper_type = None
    if hasattr(args, 'paper_type') and args.paper_type:
        paper_type = _parse_paper_type(args.paper_type)
    if paper_type:
        printer.paper_type = paper_type

    print_technology = None
    if hasattr(args, 'print_technology') and args.print_technology:
        print_technology = _parse_print_technology(args.print_technology)
    elif getattr(printer, '_PRINT_TECHNOLOGY', None) is not None:
        print_technology = printer._PRINT_TECHNOLOGY

    if print_technology is not None:
        printer.print_technology = print_technology


def _get_dpi_from_model_or_device(args) -> int:
    """Determine DPI from explicit model or discovered device metadata."""
    import pylabelprinter
    from pylabelprinter.registry import get_registration_by_model

    model_name = getattr(args, "model", None)

    if model_name:
        reg = get_registration_by_model(model_name)
        if reg and reg.dpi is not None:
            return int(reg.dpi)

    device = pylabelprinter.find_printer(
        getattr(args, "device", None),
        model=model_name,
        usb_port=getattr(args, "usb_port", None),
        serial=getattr(args, "serial", None),
    )

    if device is not None:
        if device.dpi is not None:
            return int(device.dpi)
        if device.model:
            reg = get_registration_by_model(device.model)
            if reg and reg.dpi is not None:
                return int(reg.dpi)

    raise ValueError(
        "Could not determine DPI from model metadata. "
        "Use --model or specify a device (--device/--usb-port/--serial)."
    )


def _do_print(args, image, label):
    """Shared print logic for print and print-template."""
    import pylabelprinter
    
    # Density
    density = getattr(args, 'density', 10)
    copies = getattr(args, 'copies', 1)
    x_off = getattr(args, 'x_offset', 0.0) or 0.0
    y_off = getattr(args, 'y_offset', 0.0) or 0.0
    
    with pylabelprinter.open(args.device, model=args.model, usb_port=args.usb_port, serial=args.serial) as printer:
        _configure_printer_for_job(printer, args)
        
        printer.print_image(
            image, 
            label, 
            copies=copies,
            density=density,
            x_offset_mm=x_off,
            y_offset_mm=y_off,
        )


def cmd_print_template(args):
    """Print a YAML template."""
    import pylabelprinter
    
    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: Template not found: {template_path}", file=sys.stderr)
        return 1
    
    # Parse variables (key=value)
    variables = {}
    if args.var:
        for var in args.var:
            if "=" in var:
                key, _, value = var.partition("=")
                variables[key.strip()] = value.strip()
            else:
                print(f"Warning: Invalid variable '{var}', expected key=value", file=sys.stderr)

    try:
        template = pylabelprinter.LabelTemplate.from_file(template_path, variables=variables)
    except Exception as e:
        print(f"Error loading template: {e}", file=sys.stderr)
        return 1
    
    try:
        # Render template to image
        image = pylabelprinter.render_template(template)
        label = pylabelprinter.Label(template.width_mm, template.height_mm)
        
        print(f"Printing template {template_path} ({template.width_mm}x{template.height_mm}mm)...")
        if variables:
            print(f"  Variables: {variables}")
        
        _do_print(args, image, label)
        print("Done!")
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Error: No paper loaded!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_render_template(args):
    """Render a YAML template as an image file."""
    import pylabelprinter

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: Template not found: {template_path}", file=sys.stderr)
        return 1

    # Parse variables (key=value)
    variables = {}
    if args.var:
        for var in args.var:
            if "=" in var:
                key, _, value = var.partition("=")
                variables[key.strip()] = value.strip()
            else:
                print(f"Warning: Invalid variable '{var}', expected key=value", file=sys.stderr)

    try:
        dpi = _get_dpi_from_model_or_device(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        template = pylabelprinter.LabelTemplate.from_file(template_path, variables=variables)
        image = pylabelprinter.render_template(template, dpi=dpi)
    except Exception as e:
        print(f"Error rendering template: {e}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    try:
        image.save(output_path)
    except Exception as e:
        print(f"Error saving file: {e}", file=sys.stderr)
        return 1

    print(f"Rendered: {template_path} -> {output_path} ({dpi} DPI)")
    return 0


def cmd_print(args):
    """Print an image."""
    import pylabelprinter
    from PIL import Image
    
    # Load image
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: File not found: {image_path}", file=sys.stderr)
        return 1
    
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Error loading image: {e}", file=sys.stderr)
        return 1
    
    # Parse label size
    try:
        width, height = args.label.lower().split("x")
        label = pylabelprinter.Label(float(width), float(height))
    except ValueError:
        print(f"Error: Invalid label format '{args.label}'", file=sys.stderr)
        return 1
    
    try:
        print(f"Printing {image_path} on {label}...")
        _do_print(args, image, label)
        print("Done!")
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.PrinterStandbyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except pylabelprinter.NoPaperError:
        print("Error: No paper loaded!", file=sys.stderr)
        return 1
    except pylabelprinter.LabelprinterError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="pylabelprinter",
        description="Label Printer CLI"
    )
    parser.add_argument("--device", "-d", help="Device ID or path (e.g. /dev/usb/lp0)")
    parser.add_argument("--model", "-m", help="Model name (e.g. M120, M221)")
    parser.add_argument("--usb-port", "-u", help="USB port path (e.g. 3-1.4.4)")
    parser.add_argument("--serial", "-s", help="Serial number (e.g. Q218G4C48320027)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # list
    subparsers.add_parser("list", help="List all printers")
    
    # info
    subparsers.add_parser("info", help="Show printer information")
    
    # label-size
    p_size = subparsers.add_parser("label-size", help="Show image size for a label")
    p_size.add_argument("size", help="Label size (e.g. 40x30)")
    p_size.add_argument("--dpi", type=int, default=203, help="DPI (default: 203)")
    
    # print
    p_print = subparsers.add_parser("print", help="Print an image")
    p_print.add_argument("image", help="Image file")
    p_print.add_argument("--label", "-l", required=True, help="Label size (e.g. 40x30)")
    p_print.add_argument("--copies", "-c", type=int, default=1, help="Number of copies")
    p_print.add_argument("--density", type=int, default=10, help="Print density (1-15)")
    p_print.add_argument("--paper-type", "-p", help="Paper type (AUTO_DETECT, GAP, CONTINUOUS, BLACK_MARK)")
    p_print.add_argument("--print-technology", help="Print technology (THERMAL_TRANSFER or DIRECT_THERMAL)")
    p_print.add_argument("--x-offset", type=float, default=0.0, help="Horizontal offset in mm (positive=right)")
    p_print.add_argument("--y-offset", type=float, default=0.0, help="Vertical offset in mm (positive=down)")
    
    # print-template
    p_template = subparsers.add_parser("print-template", help="Print a YAML template")
    p_template.add_argument("template", help="YAML template file")
    p_template.add_argument("--var", "-v", action="append", help="Variable (key=value), can be used multiple times")
    p_template.add_argument("--copies", "-c", type=int, default=1, help="Number of copies")
    p_template.add_argument("--density", type=int, default=10, help="Print density (1-15)")
    p_template.add_argument("--paper-type", "-p", help="Paper type (AUTO_DETECT, GAP, CONTINUOUS, BLACK_MARK)")
    p_template.add_argument("--print-technology", help="Print technology (THERMAL_TRANSFER or DIRECT_THERMAL)")
    p_template.add_argument("--x-offset", type=float, default=0.0, help="Horizontal offset in mm (positive=right)")
    p_template.add_argument("--y-offset", type=float, default=0.0, help="Vertical offset in mm (positive=down)")

    # render-template
    p_render = subparsers.add_parser("render-template", help="Render a YAML template as an image")
    p_render.add_argument("template", help="YAML template file")
    p_render.add_argument("output", help="Output image file (e.g. out.png)")
    p_render.add_argument("--var", "-v", action="append", help="Variable (key=value), can be used multiple times")
    
    # test
    p_test = subparsers.add_parser("test", help="Print a test label")
    p_test.add_argument("--label", "-l", required=True, help="Label size (e.g. 40x30)")
    p_test.add_argument("--copies", "-c", type=int, default=1, help="Number of copies")
    p_test.add_argument("--density", type=int, default=10, help="Print density (1-15)")
    p_test.add_argument("--paper-type", "-p", help="Paper type (AUTO_DETECT, GAP, CONTINUOUS, BLACK_MARK)")
    p_test.add_argument("--print-technology", help="Print technology (THERMAL_TRANSFER or DIRECT_THERMAL)")
    p_test.add_argument("--x-offset", type=float, default=0.0, help="Horizontal offset in mm (positive=right)")
    p_test.add_argument("--y-offset", type=float, default=0.0, help="Vertical offset in mm (positive=down)")
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
