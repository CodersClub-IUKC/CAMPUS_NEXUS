import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, List, TypedDict, Optional

from colorthief import ColorThief
from django.contrib.staticfiles import finders
from django.conf import settings
from django.template import Engine, Context
from PIL import Image
import colorsys

logger = logging.getLogger(__name__)

# Try locate the SCSS template safely
_TEMPLATE_FILE = finders.find("scss/_association_theme.scss")
TEMPLATE_PATH = Path(_TEMPLATE_FILE) if _TEMPLATE_FILE else None

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ShadeDict(TypedDict):
    shade_50: str
    shade_100: str
    shade_200: str
    shade_300: str
    shade_400: str
    shade_500: str
    shade_600: str
    shade_700: str
    shade_800: str
    shade_900: str


class Palette(TypedDict):
    primary: ShadeDict
    secondary: ShadeDict


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def _sanitize_hex(hex_color: Optional[str], fallback: str) -> str:
    """
    Ensure we always return a valid #RRGGBB string.
    """
    if isinstance(hex_color, str) and HEX_COLOR_RE.match(hex_color):
        return hex_color.lower()
    return fallback.lower()


def generate_color_shades(base_color_hex: str) -> ShadeDict:
    # base_color_hex must be #RRGGBB by now
    base_rgb = _hex_to_rgb(base_color_hex)
    base_hsl = colorsys.rgb_to_hls(base_rgb[0] / 255, base_rgb[1] / 255, base_rgb[2] / 255)

    shades: dict[str, str] = {}
    shade_values = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]
    shade_keys = [
        "shade_50", "shade_100", "shade_200", "shade_300", "shade_400",
        "shade_500", "shade_600", "shade_700", "shade_800", "shade_900"
    ]

    for i, (shade_value, shade_key) in enumerate(zip(shade_values, shade_keys)):
        if shade_value == 500:
            shades[shade_key] = base_color_hex
        elif shade_value < 500:
            # lighter shades
            lightness_factor = 0.95 - (i * 0.1)
            new_lightness = min(
                0.95,
                base_hsl[1] + (lightness_factor - base_hsl[1]) * (500 - shade_value) / 450
            )
            new_saturation = base_hsl[2] * (0.3 + 0.7 * shade_value / 500)

            new_rgb = colorsys.hls_to_rgb(base_hsl[0], new_lightness, new_saturation)
            shades[shade_key] = _rgb_to_hex(tuple(int(c * 255) for c in new_rgb))  # type: ignore
        else:
            # darker shades
            darkness_factor = max(0.05, base_hsl[1] * (900 - shade_value) / 400)
            new_lightness = darkness_factor
            new_saturation = min(1.0, base_hsl[2] * (1 + (shade_value - 500) / 500))

            new_rgb = colorsys.hls_to_rgb(base_hsl[0], new_lightness, new_saturation)
            shades[shade_key] = _rgb_to_hex(tuple(int(c * 255) for c in new_rgb))  # type: ignore

    return shades  # type: ignore


def render_scss(palette: Palette) -> str:
    """
    Fill the placeholders in the SCSS template with complete shade palettes.
    If template is missing, raise a controlled error (handled by caller).
    """
    if not TEMPLATE_PATH or not TEMPLATE_PATH.exists():
        raise FileNotFoundError("SCSS template scss/_association_theme.scss not found in staticfiles.")

    engine = Engine()
    tmpl = engine.from_string(TEMPLATE_PATH.read_text())

    template_context = {
        "primary_50": palette["primary"]["shade_50"],
        "primary_100": palette["primary"]["shade_100"],
        "primary_200": palette["primary"]["shade_200"],
        "primary_300": palette["primary"]["shade_300"],
        "primary_400": palette["primary"]["shade_400"],
        "primary_500": palette["primary"]["shade_500"],
        "primary_600": palette["primary"]["shade_600"],
        "primary_700": palette["primary"]["shade_700"],
        "primary_800": palette["primary"]["shade_800"],
        "primary_900": palette["primary"]["shade_900"],
        "secondary_50": palette["secondary"]["shade_50"],
        "secondary_100": palette["secondary"]["shade_100"],
        "secondary_200": palette["secondary"]["shade_200"],
        "secondary_300": palette["secondary"]["shade_300"],
        "secondary_400": palette["secondary"]["shade_400"],
        "secondary_500": palette["secondary"]["shade_500"],
        "secondary_600": palette["secondary"]["shade_600"],
        "secondary_700": palette["secondary"]["shade_700"],
        "secondary_800": palette["secondary"]["shade_800"],
        "secondary_900": palette["secondary"]["shade_900"],
    }

    ctx = Context(template_context)
    return tmpl.render(ctx)


def compile_scss(scss_source: str) -> Optional[str]:
    """
    Compile SCSS source to CSS using the 'sass' binary.
    Returns CSS string on success; None on failure (never raises).
    """
    include_dir = str(Path(settings.BASE_DIR) / "vendor")

    src_path = None
    css_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".scss", delete=False) as src:
            src.write(scss_source.encode("utf-8"))
            src_path = src.name

        css_path = src_path.replace(".scss", ".css")

        cmd = [
            "sass",
            "--no-source-map",
            "--style=compressed",
            "--load-path", include_dir,
            src_path,
            css_path,
        ]

        # capture_output lets us log real error messages
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        return Path(css_path).read_text(encoding="utf-8")

    except FileNotFoundError:
        # sass not installed
        logger.warning("SASS binary not found. Skipping theme compilation.")
        return None

    except subprocess.CalledProcessError as e:
        logger.error("SASS compilation failed (skipping theme).")
        if e.stdout:
            logger.error("SASS STDOUT:\n%s", e.stdout)
        if e.stderr:
            logger.error("SASS STDERR:\n%s", e.stderr)
        return None

    except Exception as e:
        logger.exception("Unexpected error compiling SCSS (skipping theme): %s", e)
        return None

    finally:
        # Clean temp files
        try:
            if src_path:
                Path(src_path).unlink(missing_ok=True)
            if css_path:
                Path(css_path).unlink(missing_ok=True)
        except Exception:
            pass


def build_association_theme(palette: Palette) -> Optional[str]:
    """
    Returns compiled CSS or None if anything fails.
    """
    try:
        rendered = render_scss(palette)
    except Exception as e:
        logger.error("SCSS render failed (skipping theme): %s", e)
        return None

    return compile_scss(rendered)


def _ensure_rgb(image_path: Path) -> Path:
    """
    ColorThief works best with an RGB image.
    Convert if needed and return a temp file path.
    """
    img = Image.open(image_path)
    if img.mode != "RGB":
        tmp = image_path.with_suffix(".rgb.png")
        img.convert("RGB").save(tmp, format="PNG")
        return tmp
    return image_path


def get_primary_secondary_colors(
    logo_path: Optional[Path] = None,
    num_colors: int = 6,
    fallback_colors: Tuple[str, str] = ("#3b82f6", "#64748b"),
) -> Tuple[str, str]:
    """
    Extract two dominant colours from a logo image.
    Always returns valid #RRGGBB strings (sanitized).
    """
    # ensure fallbacks are valid
    fallback_primary = _sanitize_hex(fallback_colors[0], "#3b82f6")
    fallback_secondary = _sanitize_hex(fallback_colors[1], "#64748b")

    if not logo_path:
        return fallback_primary, fallback_secondary

    safe_path = _ensure_rgb(logo_path)

    try:
        ct = ColorThief(str(safe_path))
        palette: List[Tuple[int, int, int]] = ct.get_palette(color_count=num_colors, quality=1)

        if not palette:
            return fallback_primary, fallback_secondary

        # Filter out colors too close to white or black
        filtered_colors: List[Tuple[int, int, int]] = []
        for color in palette:
            brightness = sum(color) / 3
            if 30 < brightness < 225:
                filtered_colors.append(color)

        colors_to_use = filtered_colors if len(filtered_colors) >= 2 else palette

        primary_hex = _rgb_to_hex(colors_to_use[0])
        secondary_hex = _rgb_to_hex(colors_to_use[1]) if len(colors_to_use) > 1 else primary_hex

        # sanitize in case anything weird happened
        primary_hex = _sanitize_hex(primary_hex, fallback_primary)
        secondary_hex = _sanitize_hex(secondary_hex, fallback_secondary)

        return primary_hex, secondary_hex

    except Exception as e:
        logger.error("Error extracting colors from logo (using fallback): %s", e)
        return fallback_primary, fallback_secondary

    finally:
        # Clean conversion file if created
        if safe_path != logo_path:
            try:
                safe_path.unlink(missing_ok=True)
            except Exception:
                pass


def generate_complete_palette(primary_hex: str, secondary_hex: str) -> Palette:
    primary_shades = generate_color_shades(primary_hex)
    secondary_shades = generate_color_shades(secondary_hex)

    return Palette(
        primary=primary_shades,
        secondary=secondary_shades,
    )


def get_association_theme(association) -> Optional[str]:
    """
    Returns compiled CSS for this association or None (never raises).
    """
    if not getattr(association, "logo_image", None):
        return None  # fall back to default theme

    fallback = getattr(settings, "ASSOCIATION_DEFAULT_THEME", ("#3b82f6", "#64748b"))

    try:
        primary_color, secondary_color = get_primary_secondary_colors(
            Path(association.logo_image.path),
            fallback_colors=fallback,
        )
    except Exception as e:
        logger.error("Theme generation failed while reading logo (using fallback): %s", e)
        primary_color, secondary_color = _sanitize_hex(fallback[0], "#3b82f6"), _sanitize_hex(fallback[1], "#64748b")

    palette = generate_complete_palette(primary_color, secondary_color)

    css = build_association_theme(palette)
    return css
