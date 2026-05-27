# pylabelprinter

Python library and CLI for thermal label printers.

`pylabelprinter` currently focuses on USB-connected Phomemo label printers and
provides three main building blocks:

- printer discovery and status queries
- image printing
- YAML-based label templates

## Current scope

### Supported printers

- `Phomemo M120`
- `Phomemo M221`

### What it can do

- discover supported USB printers
- query printer information such as firmware, serial number, battery and paper state
- configure paper type, auto-off time and print density
- print PIL images on labels
- render and print YAML label templates

### Current limitations

- currently Linux-oriented
- currently USB-oriented
- currently focused on supported Phomemo models only
- no promise of cross-platform support yet

## Installation

```bash
pip install pylabelprinter

# Optional USB dependency
pip install pylabelprinter[usb]
```

## Python usage

### Open the first supported printer

```python
from PIL import Image

import pylabelprinter
from pylabelprinter import Label

with pylabelprinter.open() as printer:
		print(f"Model: {printer.model}")
		print(f"Firmware: {printer.firmware_version}")
		print(f"Battery: {printer.battery_level}")
		print(f"Paper loaded: {printer.has_paper}")

		image = Image.open("label.png")
		printer.print_image(image, Label(30, 20))
```

### Open a specific model

```python
import pylabelprinter

with pylabelprinter.open(model="M221") as printer:
		info = printer.get_info()
		print(info)
```

### Direct driver usage

```python
from PIL import Image

from pylabelprinter import Label
from pylabelprinter.printers import PhomemoM221

printer = PhomemoM221.find_usb()
printer.connect()
try:
		image = Image.open("label.png")
		printer.print_image(image, Label(30, 20), copies=1)
finally:
		printer.disconnect()
```

## CLI usage

After installation, the `pylabelprinter` command is available.

### List supported printers

```bash
pylabelprinter list
```

### Show printer information

```bash
pylabelprinter info --model M221
```

### Print an image

```bash
pylabelprinter print label.png --label 30x20 --model M221
```

### Print a test label

```bash
pylabelprinter test --label 30x20 --model M221
```

### Render a template to an image

```bash
pylabelprinter render-template label.yaml out.png --model M221
```

### Print a template

```bash
pylabelprinter print-template label.yaml --model M221 --var name=Widget --var code=1234
```

## YAML templates

Supported template elements:

- `text`
- `line`
- `qrcode`

Notes:

- text positioning uses `top`/`bottom` by default
- use `baseline: true` to interpret vertical position as text baseline
- line elements use `start` and `end` points plus optional `width`
- template variables can be passed from Python or CLI

Example:

```yaml
label:
	width: 70mm
	height: 80mm

elements:
	- type: line
		start:
			x: 25mm
			y: 0mm
		end:
			x: 25mm
			y: 80mm
		width: 0.5mm

	- type: text
		left: 4mm
		top: 15mm
		baseline: true
		size: 3mm
		text: "{name}"

	- type: qrcode
		left: 35mm
		top: 10mm
		width: 20mm
		data: "{code}"
```

Python rendering example:

```python
from pylabelprinter import render_template

image = render_template("""
label:
	width: 30mm
	height: 20mm
elements:
	- type: text
		left: 2mm
		top: 10mm
		text: "{name}"
""", variables={"name": "Demo"})
```

## Development

```bash
cd pylabelprinter
pip install -e ".[dev]"
pytest
```

## License

MIT License
