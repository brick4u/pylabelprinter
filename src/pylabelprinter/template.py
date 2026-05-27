"""
Template-Engine für Label-Definition via YAML.

Unterstützte Elemente:
- text: Text mit Größe und Positionierung
    - optional `baseline: true`, um `top`/`bottom` als Text-Baseline zu interpretieren
- line: Linie mit Start-/Endpunkt und Dicke
- qrcode: QR-Code mit Größe und Daten
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml
from PIL import Image, ImageDraw, ImageFont

# Optionale Imports für Barcodes
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


@dataclass
class LabelTemplate:
    """Geparste Label-Template Definition."""
    width_mm: float
    height_mm: float
    elements: List[Dict[str, Any]]
    
    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "LabelTemplate":
        """Erzeuge Template aus geparsten YAML-Daten."""
        label = data.get("label", {}) if isinstance(data, dict) else {}
        width = parse_dimension(label.get("width", "40mm"))
        height = parse_dimension(label.get("height", "30mm"))
        elements = data.get("elements", []) if isinstance(data, dict) else []
        return cls(width_mm=width, height_mm=height, elements=elements)
    
    @classmethod
    def from_yaml(cls, yaml_content: str, variables: Optional[Dict[str, Any]] = None) -> "LabelTemplate":
        """Parse YAML-String zu LabelTemplate."""
        data = yaml.safe_load(yaml_content)
        if variables:
            data = _substitute_in_obj(data, variables)
        return cls.from_data(data)
    
    @classmethod
    def from_file(cls, path: Union[str, Path], variables: Optional[Dict[str, Any]] = None) -> "LabelTemplate":
        """Lade Template aus YAML-Datei."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_yaml(f.read(), variables=variables)


def parse_dimension(value: Union[str, int, float]) -> float:
    """Parse Dimension mit Einheit (z.B. '40mm', '2.5mm') zu mm."""
    if isinstance(value, (int, float)):
        return float(value)
    
    match = re.match(r"^([\d.]+)\s*(mm|pt|px)?$", str(value).strip())
    if not match:
        raise ValueError(f"Invalid dimension: {value}")
    
    num = float(match.group(1))
    unit = match.group(2) or "mm"
    
    if unit == "mm":
        return num
    elif unit == "pt":
        return num * 25.4 / 72  # 72pt = 1 inch
    elif unit == "px":
        return num * 25.4 / 203  # Assuming 203 DPI
    
    return num


def mm_to_px(mm: float, dpi: int = 203) -> int:
    """Konvertiere mm zu Pixel."""
    return int(mm * dpi / 25.4)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _substitute_in_obj(value: Any, variables: Dict[str, Any]) -> Any:
    """Ersetze Variablen rekursiv in Strings innerhalb von Datenstrukturen."""
    if isinstance(value, str):
        return value.format_map(_SafeFormatDict(variables))
    if isinstance(value, list):
        return [_substitute_in_obj(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _substitute_in_obj(v, variables) for k, v in value.items()}
    return value


class TemplateRenderer:
    """Rendert ein LabelTemplate zu einem PIL Image."""
    
    def __init__(self, dpi: int = 203):
        self.dpi = dpi
        self._font_cache: Dict[int, ImageFont.FreeTypeFont] = {}
    
    def render(self, template: LabelTemplate) -> Image.Image:
        """Rendere Template zu PIL Image."""
        # Bildgröße berechnen
        width_px = mm_to_px(template.width_mm, self.dpi)
        height_px = mm_to_px(template.height_mm, self.dpi)
        
        # Weißes Bild erstellen
        image = Image.new("L", (width_px, height_px), 255)
        draw = ImageDraw.Draw(image)
        
        # Elemente rendern
        for element in template.elements:
            element_type = element.get("type", "").lower()
            
            if element_type == "text":
                self._render_text(image, draw, element, template)
            elif element_type == "line":
                self._render_line(draw, element)
            elif element_type == "qrcode":
                self._render_qrcode(image, element, template)
            else:
                raise ValueError(f"Unknown element type: {element_type}")
        
        return image
    
    def _get_position(
        self, 
        element: Dict[str, Any], 
        template: LabelTemplate,
        element_width_px: int = 0,
        element_height_px: int = 0,
    ) -> Tuple[int, int]:
        """Berechne Pixel-Position aus left/right/top/bottom."""
        label_width_px = mm_to_px(template.width_mm, self.dpi)
        label_height_px = mm_to_px(template.height_mm, self.dpi)
        
        # X-Position
        if "left" in element:
            x = mm_to_px(parse_dimension(element["left"]), self.dpi)
        elif "right" in element:
            right = mm_to_px(parse_dimension(element["right"]), self.dpi)
            x = label_width_px - right - element_width_px
        else:
            x = 0
        
        # Y-Position (Koordinatensystem: top=0)
        if "top" in element:
            y = mm_to_px(parse_dimension(element["top"]), self.dpi)
        elif "bottom" in element:
            bottom = mm_to_px(parse_dimension(element["bottom"]), self.dpi)
            y = label_height_px - bottom - element_height_px
        else:
            y = 0
        
        return x, y
    
    def _get_bundled_font_path(self) -> str:
        """Pfad zur mitgelieferten DejaVu Sans Schrift."""
        import os
        return os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    
    def _get_font(self, size_mm: float, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Hole oder erstelle Font für gegebene Größe in mm."""
        size_px = mm_to_px(size_mm, self.dpi)
        cache_key = (size_px, bold)
        
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]
        
        # Zuerst: Mitgelieferte Schrift
        import os
        bundled_font = os.path.join(
            os.path.dirname(__file__), 
            "fonts", 
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        )
        
        font_paths = [bundled_font]
        
        # Fallback: System-Fonts
        font_paths.extend([
            # DejaVu (Debian/Ubuntu)
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # Noto (weit verbreitet)
            "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            # Liberation (RHEL/Fedora)
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])
        
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, size_px)
                break
            except (OSError, IOError):
                continue
        
        if font is None:
            raise RuntimeError(
                f"No font found. Install a TrueType font like 'ttf-dejavu' or 'noto-fonts'. "
                f"Searched paths: {font_paths}"
            )
        
        self._font_cache[cache_key] = font
        return font
    
    def _render_text(
        self, 
        image: Image.Image, 
        draw: ImageDraw.ImageDraw, 
        element: Dict[str, Any],
        template: LabelTemplate,
    ) -> None:
        """Rendere Text-Element."""
        text = str(element.get("text", ""))
        size_mm = parse_dimension(element.get("size", "3mm"))
        use_baseline = bool(element.get("baseline", False))
        is_multiline = "\n" in text
        anchor = "ls" if use_baseline else None
        bbox_fn = draw.multiline_textbbox if is_multiline else draw.textbbox
        draw_fn = draw.multiline_text if is_multiline else draw.text
        
        font = self._get_font(size_mm)
        
        # Text-Größe berechnen
        bbox_kwargs: Dict[str, Any] = {"font": font}
        if anchor is not None:
            bbox_kwargs["anchor"] = anchor
        bbox = bbox_fn((0, 0), text, **bbox_kwargs)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Position berechnen
        x, y = self._get_position(element, template, text_width, text_height)

        if not use_baseline:
            x -= bbox[0]
            y -= bbox[1]

        if use_baseline and "top" in element:
            y = mm_to_px(parse_dimension(element["top"]), self.dpi)
        elif use_baseline and "bottom" in element:
            label_height_px = mm_to_px(template.height_mm, self.dpi)
            bottom = mm_to_px(parse_dimension(element["bottom"]), self.dpi)
            y = label_height_px - bottom - bbox[3]
        
        # Text zeichnen
        draw_kwargs: Dict[str, Any] = {"fill": 0, "font": font}
        if anchor is not None:
            draw_kwargs["anchor"] = anchor
        draw_fn((x, y), text, **draw_kwargs)

    def _render_line(
        self,
        draw: ImageDraw.ImageDraw,
        element: Dict[str, Any],
    ) -> None:
        """Rendere Linien-Element."""
        start = element.get("start", {})
        end = element.get("end", {})

        if not isinstance(start, dict) or not isinstance(end, dict):
            raise ValueError("Line element requires 'start' and 'end' objects")
        if "x" not in start or "y" not in start or "x" not in end or "y" not in end:
            raise ValueError("Line element requires start.x, start.y, end.x, end.y")

        x1 = mm_to_px(parse_dimension(start["x"]), self.dpi)
        y1 = mm_to_px(parse_dimension(start["y"]), self.dpi)
        x2 = mm_to_px(parse_dimension(end["x"]), self.dpi)
        y2 = mm_to_px(parse_dimension(end["y"]), self.dpi)
        width = max(1, mm_to_px(parse_dimension(element.get("width", "1px")), self.dpi))

        draw.line((x1, y1, x2, y2), fill=0, width=width)
    
    def _render_qrcode(
        self, 
        image: Image.Image, 
        element: Dict[str, Any],
        template: LabelTemplate,
    ) -> None:
        """Rendere QR-Code Element."""
        if not HAS_QRCODE:
            raise ImportError("qrcode library required: pip install qrcode[pil]")
        
        data = str(element.get("data", ""))
        
        # Größe
        width_mm = parse_dimension(element.get("width", "10mm"))
        height_mm = parse_dimension(element.get("height", width_mm))
        width_px = mm_to_px(width_mm, self.dpi)
        height_px = mm_to_px(height_mm, self.dpi)
        
        # QR-Code generieren
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=0,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        qr_image = qr_image.convert("L")
        qr_image = qr_image.resize((width_px, height_px), Image.Resampling.NEAREST)
        
        # Position berechnen
        x, y = self._get_position(element, template, width_px, height_px)
        
        # QR-Code einfügen
        image.paste(qr_image, (x, y))


def render_template(
    template: Union[str, Path, LabelTemplate],
    dpi: int = 203,
    variables: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Rendere Template zu PIL Image.
    
    Args:
        template: YAML-String, Dateipfad, oder LabelTemplate-Objekt
        dpi: Auflösung für Rendering
        
    Returns:
        PIL Image im Grayscale-Modus
    """
    if isinstance(template, LabelTemplate):
        if variables:
            elements = _substitute_in_obj(template.elements, variables)
            tpl = LabelTemplate(
                width_mm=template.width_mm,
                height_mm=template.height_mm,
                elements=elements,
            )
        else:
            tpl = template
    elif isinstance(template, Path) or (isinstance(template, str) and Path(template).exists()):
        tpl = LabelTemplate.from_file(template, variables=variables)
    else:
        tpl = LabelTemplate.from_yaml(template, variables=variables)
    
    renderer = TemplateRenderer(dpi=dpi)
    return renderer.render(tpl)


def print_template(
    printer,
    template: Union[str, Path, LabelTemplate],
    copies: int = 1,
    density=None,
    variables: Optional[Dict[str, Any]] = None,
) -> None:
    """Rendere und drucke ein Template.
    
    Args:
        printer: Geöffnete Printer-Instanz
        template: YAML-String, Dateipfad, oder LabelTemplate-Objekt
        copies: Anzahl Kopien
        density: Optionale Druckdichte
    """
    from .label import Label
    
    # Template laden/parsen
    if isinstance(template, LabelTemplate):
        if variables:
            elements = _substitute_in_obj(template.elements, variables)
            tpl = LabelTemplate(
                width_mm=template.width_mm,
                height_mm=template.height_mm,
                elements=elements,
            )
        else:
            tpl = template
    elif isinstance(template, Path) or (isinstance(template, str) and Path(template).exists()):
        tpl = LabelTemplate.from_file(template, variables=variables)
    else:
        tpl = LabelTemplate.from_yaml(template, variables=variables)
    
    # Label erstellen
    label = Label(tpl.width_mm, tpl.height_mm)
    
    # Rendern
    renderer = TemplateRenderer(dpi=printer.dpi)
    image = renderer.render(tpl)
    
    # Drucken
    printer.print_image(image, label, copies=copies, density=density)
