"""
Test-Label Generator für pylabelprinter.

Generiert ein standardisiertes Test-Label zur Überprüfung von:
- Druckqualität
- Ausrichtung/Zentrierung
- Label-Größe
"""

from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple

from .label import Label, ImageSize


def create_test_label(
    size: ImageSize,
    model: str = "Unknown",
    label: Optional[Label] = None,
    margin_mm: int = 2,
    dpi: int = 203,
) -> Image.Image:
    """Erstelle ein Test-Label mit Rahmen, Kreuz und Info-Text.
    
    Das Test-Label enthält:
    - 3-fachen Rahmen (außen, mittig, innen)
    - Diagonales Kreuz durch die Mitte
    - Text: "pylabelprinter", Druckermodell, Label-Größe
    
    Args:
        size: Bildgröße in Pixel (von printer.get_image_size())
        model: Druckermodell-Name
        label: Label-Objekt für Größenanzeige
        margin_mm: Abstand zwischen Rahmen in mm
        dpi: Auflösung für mm-Berechnung
        
    Returns:
        PIL Image im Grayscale-Modus
    """
    width, height = size.width, size.height
    
    # Bild erstellen (weiß)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    
    # Margin in Pixel
    margin = int(margin_mm * dpi / 25.4)
    
    # === 3-facher Rahmen ===
    # Äußerer Rahmen
    draw.rectangle([0, 0, width - 1, height - 1], outline=0, width=1)
    
    # Mittlerer Rahmen
    draw.rectangle(
        [margin, margin, width - 1 - margin, height - 1 - margin],
        outline=0, width=1
    )
    
    # Innerer Rahmen
    draw.rectangle(
        [2 * margin, 2 * margin, width - 1 - 2 * margin, height - 1 - 2 * margin],
        outline=0, width=1
    )
    
    # === Kreuz in der Mitte ===
    # Diagonalen
    inner_left = 2 * margin + 1
    inner_top = 2 * margin + 1
    inner_right = width - 2 * margin - 2
    inner_bottom = height - 2 * margin - 2
    
    draw.line([inner_left, inner_top, inner_right, inner_bottom], fill=0, width=1)
    draw.line([inner_right, inner_top, inner_left, inner_bottom], fill=0, width=1)
    
    # Horizontale und vertikale Mittellinien
    center_x = width // 2
    center_y = height // 2
    draw.line([inner_left, center_y, inner_right, center_y], fill=0, width=1)
    draw.line([center_x, inner_top, center_x, inner_bottom], fill=0, width=1)
    
    # === Text ===
    # Versuche eine Schriftart zu laden
    font = None
    font_small = None
    try:
        # Versuche TrueType-Font
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 11)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except (OSError, IOError):
            # Fallback: Default-Font
            font = ImageFont.load_default()
            font_small = font
    
    # Text-Positionen (im inneren Bereich, aber nicht auf dem Kreuz)
    text_x = 3 * margin
    text_y_start = 3 * margin
    line_height = 16
    
    # Hintergrund für Text (weiße Box)
    text_lines = [model]
    if label:
        text_lines.append(f"{label.width_mm}x{label.height_mm}mm")
    
    # Berechne Text-Box Größe
    max_text_width = 0
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_text_width = max(max_text_width, bbox[2] - bbox[0])
    
    text_box_height = len(text_lines) * line_height + 4
    
    # Weiße Box hinter Text
    draw.rectangle(
        [text_x - 2, text_y_start - 2, 
         text_x + max_text_width + 4, text_y_start + text_box_height],
        fill=255, outline=0, width=1
    )
    
    # Text zeichnen
    y = text_y_start
    draw.text((text_x, y), model, fill=0, font=font)
    y += line_height
    
    if label:
        draw.text((text_x, y), f"{label.width_mm}x{label.height_mm}mm", fill=0, font=font_small)
    
    return image


def print_test_label(
    printer,
    label: Label,
    density=None,
    copies: int = 1,
) -> None:
    """Drucke ein Test-Label auf dem angegebenen Drucker.
    
    Args:
        printer: Geöffnete Printer-Instanz
        label: Label-Größe
        density: Optionale Druckdichte
        copies: Anzahl Kopien
    """
    size = printer.get_image_size(label)
    image = create_test_label(
        size=size,
        model=printer.model,
        label=label,
        dpi=printer.dpi,
    )
    
    printer.print_image(image, label, copies=copies, density=density)
