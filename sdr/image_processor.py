"""
Post-processing for decoded satellite images.
Applies colormaps, generates thumbnails, rotates, and adds watermarks.
All operations create new files and preserve originals.
"""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def process_satdump_layers(layers: dict[str, Path]) -> dict[str, Path]:
    """
    Process the dictionary of images returned by SatDump.
    For now, it just generates a thumbnail for the best available layer (e.g. msa).
    """
    if not layers:
        return {}
        
    result = layers.copy()
    
    # Pick the best layer to generate a thumbnail from
    best_layer_key = None
    for pref in ["msa", "mcir", "1"]:
        if pref in layers:
            best_layer_key = pref
            break
    
    if not best_layer_key:
        best_layer_key = list(layers.keys())[0]
        
    thumb_path = generate_thumbnail(layers[best_layer_key])
    result["thumb"] = thumb_path
    
    return result


def apply_colormap(image_path: Path, colormap: str | None = None) -> Path:
    """
    Apply a colormap to a grayscale satellite image.

    Args:
        image_path: Path to the source image.
        colormap: Colormap name ("thermal", "grey", "rainbow", "contrast").
                  If None, reads from config.

    Returns:
        Path to the colorized image.
    """
    cfg = get_config()
    colormap = colormap or cfg.image.get("colormap", "grey")
    image_path = Path(image_path)

    img = Image.open(image_path).convert("L")  # Ensure grayscale
    output_name = f"{image_path.stem}_{colormap}{image_path.suffix}"
    output_path = image_path.parent / output_name

    if colormap == "grey":
        img.save(output_path)
    elif colormap == "thermal":
        img = _apply_thermal_lut(img)
        img.save(output_path)
    elif colormap == "rainbow":
        img = _apply_rainbow_lut(img)
        img.save(output_path)
    elif colormap == "contrast":
        from PIL import ImageOps
        img = ImageOps.autocontrast(img, cutoff=2)
        img.save(output_path)
    else:
        logger.warning(f"Unknown colormap '{colormap}', saving grayscale")
        img.save(output_path)

    logger.info(f"Applied colormap '{colormap}': {output_path}")
    return output_path


def _apply_thermal_lut(img: Image.Image) -> Image.Image:
    """Apply a blue-to-red thermal colormap."""
    rgb = Image.new("RGB", img.size)
    pixels = img.load()
    rgb_pixels = rgb.load()

    for y in range(img.height):
        for x in range(img.width):
            v = pixels[x, y]
            # Blue (cold) → White → Red (hot)
            if v < 128:
                r = 0
                g = int(v * 2)
                b = 255 - int(v * 2)
            else:
                r = int((v - 128) * 2)
                g = 255 - int((v - 128) * 2)
                b = 0
            rgb_pixels[x, y] = (min(r, 255), min(g, 255), min(b, 255))

    return rgb


def _apply_rainbow_lut(img: Image.Image) -> Image.Image:
    """Apply a rainbow (HSV hue sweep) colormap."""
    import colorsys

    rgb = Image.new("RGB", img.size)
    pixels = img.load()
    rgb_pixels = rgb.load()

    for y in range(img.height):
        for x in range(img.width):
            v = pixels[x, y] / 255.0
            r, g, b = colorsys.hsv_to_rgb(v * 0.7, 0.9, 0.9)
            rgb_pixels[x, y] = (int(r * 255), int(g * 255), int(b * 255))

    return rgb


def generate_thumbnail(image_path: Path) -> Path:
    """
    Generate a thumbnail of the satellite image.

    Args:
        image_path: Path to the source image.

    Returns:
        Path to the thumbnail image.
    """
    cfg = get_config()
    thumb_size = tuple(cfg.image.get("thumbnail_size", [320, 240]))
    image_path = Path(image_path)

    output_name = f"{image_path.stem}_thumb{image_path.suffix}"
    output_path = image_path.parent / output_name

    img = Image.open(image_path)
    img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
    img.save(output_path)

    logger.debug(f"Generated thumbnail: {output_path}")
    return output_path


def rotate_for_pass_direction(image_path: Path, is_northbound: bool) -> Path:
    """
    Rotate image 180° for descending (southbound) passes so north is up.

    Args:
        image_path: Path to the source image.
        is_northbound: True if satellite was traveling north.

    Returns:
        Path to the rotated image (same path if northbound, new file if rotated).
    """
    image_path = Path(image_path)

    if is_northbound:
        return image_path

    output_name = f"{image_path.stem}_rotated{image_path.suffix}"
    output_path = image_path.parent / output_name

    img = Image.open(image_path)
    img = img.rotate(180)
    img.save(output_path)

    logger.info(f"Rotated image for southbound pass: {output_path}")
    return output_path


def add_metadata_watermark(image_path: Path, metadata: dict) -> Path:
    """
    Add text watermark with pass metadata to the image.

    Args:
        image_path: Path to the source image.
        metadata: Dict with keys like satellite_name, pass_time, max_elevation.

    Returns:
        Path to the watermarked image.
    """
    image_path = Path(image_path)
    output_name = f"{image_path.stem}_watermark{image_path.suffix}"
    output_path = image_path.parent / output_name

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Build watermark text
    lines = []
    if "satellite_name" in metadata:
        lines.append(f"Satellite: {metadata['satellite_name']}")
    if "pass_time" in metadata:
        lines.append(f"Time: {metadata['pass_time']}")
    if "max_elevation" in metadata:
        lines.append(f"Max El: {metadata['max_elevation']}°")

    text = "\n".join(lines)

    # Use default font (Pillow built-in)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Draw text with a dark background for readability
    text_bbox = draw.multiline_textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    padding = 8
    x = img.width - text_w - padding * 2 - 10
    y = img.height - text_h - padding * 2 - 10

    # Semi-transparent background
    bg = Image.new("RGBA", (text_w + padding * 2, text_h + padding * 2), (0, 0, 0, 180))
    img.paste(
        Image.alpha_composite(
            Image.new("RGBA", bg.size, (0, 0, 0, 0)), bg
        ).convert("RGB"),
        (x, y),
    )

    draw = ImageDraw.Draw(img)
    draw.multiline_text((x + padding, y + padding), text, fill="white", font=font)
    img.save(output_path)

    logger.info(f"Added metadata watermark: {output_path}")
    return output_path
