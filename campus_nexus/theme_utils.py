import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, List, TypedDict
from colorthief import ColorThief
from django.contrib.staticfiles import finders
from django.conf import settings
from django.template import Engine, Context
from PIL import Image
import colorsys
from typing import Optional

TEMPLATE_PATH = Path(finders.find("scss/_association_theme.scss"))

class ShadeDict(TypedDict):
    """Type hint for a complete shade palette (50-900)"""
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
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def generate_color_shades(base_color_hex: str) -> ShadeDict:
    base_rgb = _hex_to_rgb(base_color_hex)
    base_hsl = colorsys.rgb_to_hls(base_rgb[0]/255, base_rgb[1]/255, base_rgb[2]/255)
    
    shades = {}
    shade_values = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]
    shade_keys = ['shade_50', 'shade_100', 'shade_200', 'shade_300', 'shade_400', 
                  'shade_500', 'shade_600', 'shade_700', 'shade_800', 'shade_900']
    
    for i, (shade_value, shade_key) in enumerate(zip(shade_values, shade_keys)):
        if shade_value == 500:
            # Use the base color for 500
            shades[shade_key] = base_color_hex
        elif shade_value < 500:
            # Lighter shades - increase lightness while decreasing saturation
            lightness_factor = 0.95 - (i * 0.1)
            new_lightness = min(0.95, base_hsl[1] + (lightness_factor - base_hsl[1]) * (500 - shade_value) / 450)
            new_saturation = base_hsl[2] * (0.3 + 0.7 * shade_value / 500)
            
            new_rgb = colorsys.hls_to_rgb(base_hsl[0], new_lightness, new_saturation)
            new_rgb = tuple(int(c * 255) for c in new_rgb)
            shades[shade_key] = _rgb_to_hex(new_rgb)
        else:
            # Darker shades - decrease lightness while increasing saturation
            darkness_factor = max(0.05, base_hsl[1] * (900 - shade_value) / 400)
            new_lightness = darkness_factor
            new_saturation = min(1.0, base_hsl[2] * (1 + (shade_value - 500) / 500))
            
            new_rgb = colorsys.hls_to_rgb(base_hsl[0], new_lightness, new_saturation)
            new_rgb = tuple(int(c * 255) for c in new_rgb)
            shades[shade_key] = _rgb_to_hex(new_rgb)
    
    return shades

def render_scss(palette: Palette) -> str:
    """
    Fill the placeholders in the SCSS template with complete shade palettes.
    """
    engine = Engine()
    tmpl = engine.from_string(TEMPLATE_PATH.read_text())
    
    template_context = {
        # Primary shades
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
        
        # Secondary shades
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

def compile_scss(scss_source: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".scss", delete=False) as src:
        src.write(scss_source.encode())
        src_path = src.name

    css_path = src_path.replace(".scss", ".css")
    include_dir = str(Path(settings.BASE_DIR) / "vendor")

    subprocess.run(
        [
            "sass",
            "--no-source-map",
            "--style=compressed",
            "--load-path", include_dir,
            src_path,
            css_path,
        ],
        check=True,
    )
    return Path(css_path).read_text()

def build_association_theme(palette: Palette) -> str:
    rendered = render_scss(palette)
    return compile_scss(rendered)

def _ensure_rgb(image_path: Path) -> Path:
    """
    ColorThief works best with an RGB image.
    If the uploaded file is in a mode other than RGB (e.g. palette or CMYK),
    Pillow converts it and saves a temporary copy.
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
    fallback_colors = ("#3b82f6", "#64748b") # Default blue and gray
) -> Tuple[str, str]:
    """
    Extract the two most dominant colours from a logo image.
    """
    # Ensure the image is in RGB mode for reliable extraction
    safe_path = _ensure_rgb(logo_path)

    try:
        ct = ColorThief(str(safe_path))
        palette: List[Tuple[int, int, int]] = ct.get_palette(color_count=num_colors, quality=1)

        # Fallback to default colors if extraction fails
        if not palette:
            return  fallback_colors

        # Filter out colors too close to white or black
        filtered_colors = []
        for color in palette:
            brightness = sum(color) / 3
            if 30 < brightness < 225:  # Avoid very light and very dark colors
                filtered_colors.append(color)
        
        # Use filtered colors if available, otherwise use original palette
        colors_to_use = filtered_colors if len(filtered_colors) >= 2 else palette
        
        primary_hex = _rgb_to_hex(colors_to_use[0])
        secondary_hex = _rgb_to_hex(colors_to_use[1]) if len(colors_to_use) > 1 else _rgb_to_hex(colors_to_use[0])

        return primary_hex, secondary_hex
        
    except Exception as e:
        print(f"Error extracting colors: {e}")
        return fallback_colors
        
    finally:
        # Clean up temporary conversion file if we created one
        if safe_path != logo_path:
            safe_path.unlink(missing_ok=True)

def generate_complete_palette(primary_hex: str, secondary_hex: str) -> Palette:
    primary_shades = generate_color_shades(primary_hex)
    secondary_shades = generate_color_shades(secondary_hex)
    
    return Palette(
        primary=primary_shades,
        secondary=secondary_shades
    )


def get_association_theme(association) -> str:
    from django.conf import settings
    
    if not association.logo_image:
        return # We shall default to the default theme(blue and gray)
    # Extract dominant colors from logo
    primary_color, secondary_color = get_primary_secondary_colors(Path(association.logo_image.path), fallback_colors=settings.ASSOCIATION_DEFAULT_THEME)
    
    # Generate complete shade palettes
    palette = generate_complete_palette(primary_color, secondary_color)
    
    # Build CSS from palette
    css = build_association_theme(palette)
    return css
