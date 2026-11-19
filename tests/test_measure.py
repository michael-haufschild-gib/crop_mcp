"""Known geometry on cluttered screens, including holes and disconnected equal fills."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tools.crop import crop_image, image_info
from tools.measure import measure_fill


def test_fill_excludes_disconnected_swatch_and_includes_holes() -> None:
    img = Image.new("RGBA", (149, 83), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((29, 14, 97, 61), fill="#ad754c")
    d.rectangle((42, 26, 59, 37), fill="white")
    d.rectangle((98, 62, 128, 72), fill="#ad754c")  # diagonal-only contact
    result = measure_fill(img, (29 / 149, 14 / 83))
    assert result["bounds_px"] == [29, 14, 98, 62]
    assert result["width"] == 69 and result["height"] == 48


def test_invalid_measurement_point(tmp_path: Path) -> None:
    path = tmp_path / "source.png"
    Image.new("RGB", (64, 48)).save(path)
    with pytest.raises(ValueError, match="measure_at"):
        image_info(str(path), [2, 0])


def test_measurement_crop_and_colors_share_display_orientation(tmp_path: Path) -> None:
    from tools.colors import extract_colors

    source = Image.new("RGB", (120, 80), "navy")
    source.paste("red", (0, 0, 24, 80))
    exif = Image.Exif()
    exif[274] = 6  # display rotated clockwise
    path = tmp_path / "rotated.png"
    source.save(path, exif=exif)
    info = image_info(str(path), [0.5, 0.1])
    assert (info["width"], info["height"]) == (80, 120)
    assert info["measured_fill"]["bounds_px"] == [0, 0, 80, 24]
    crop = crop_image(str(path), 0, 0, 1, 0.2, padding=0)
    with Image.open(crop["output_path"]) as output:
        assert output.getcolors() == [(80 * 24, (255, 0, 0))]
    result = extract_colors(str(path), 1, 0, 0, 1, 0.2)
    assert result["colors"][0]["hex"] == "#FF0000"
    assert result["region_px"] == [0, 0, 80, 24]
