from pylabelprinter.template import mm_to_px, render_template


def _black_pixel_rows(image):
    width, height = image.size
    pixels = image.load()
    rows = []

    for y in range(height):
        for x in range(width):
            if pixels[x, y] < 255:
                rows.append(y)
                break

    return rows


def test_text_baseline_moves_text_up_for_same_y():
    yaml_top = """
label:
  width: 30mm
  height: 20mm

elements:
  - type: text
    left: 2mm
    top: 18mm
    size: 3mm
    text: "gyp"
"""

    yaml_baseline = """
label:
  width: 30mm
  height: 20mm

elements:
  - type: text
    left: 2mm
    top: 18mm
    baseline: true
    size: 3mm
    text: "gyp"
"""

    image_top = render_template(yaml_top)
    image_baseline = render_template(yaml_baseline)

    rows_top = _black_pixel_rows(image_top)
    rows_baseline = _black_pixel_rows(image_baseline)

    assert rows_top
    assert rows_baseline
    assert max(rows_baseline) < max(rows_top)


def test_text_baseline_keeps_bottom_margin_inside_label():
    yaml_baseline = """
label:
  width: 30mm
  height: 20mm

elements:
  - type: text
    left: 2mm
    top: 18mm
    baseline: true
    size: 3mm
    text: "gyp"
"""

    image_baseline = render_template(yaml_baseline)
    rows_baseline = _black_pixel_rows(image_baseline)

    assert rows_baseline
    assert max(rows_baseline) < image_baseline.height - 1


def test_line_element_draws_vertical_line():
    yaml_line = """
label:
  width: 30mm
  height: 20mm

elements:
  - type: line
    start:
      x: 10mm
      y: 0mm
    end:
      x: 10mm
      y: 20mm
    width: 1mm
"""

    image = render_template(yaml_line)
    pixels = image.load()
    x = mm_to_px(10)

    black_pixels = 0
    for y in range(image.height):
        if pixels[x, y] < 255:
            black_pixels += 1

    assert black_pixels > image.height // 2


def test_multiline_text_renders_without_error():
    yaml_text = """
label:
  width: 40mm
  height: 30mm

elements:
  - type: text
    left: 2mm
    top: 17mm
    size: 6mm
    text: |
      EBRC3025
      490024
"""

    image = render_template(yaml_text)

    assert _black_pixel_rows(image)
