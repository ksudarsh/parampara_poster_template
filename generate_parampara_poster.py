# build_poster_from_xlsx.py
# A2 grid poster generator with strict banner height cap, auto-fit grid, and diacritic-safe fonts
# Output:
#   Sri_Parakala_Matham_Guru_Parampara_GRID_A2.png  (6 columns; larger text)
#
# Order:
#   17 Founders/Early Āchāryas (F01..F17*.png, sorted)  --> big section header: "Sri Parakāla Jeeyars"
#   36 Parakāla Jeeyars (0100..3600*.png, sorted)
#
# Notes:
#   - Captions taken AS-IS from Excel (two tabs)
#   - Banner is feather-blended + warm gold tinted with a STRICT height cap
#   - No border is drawn (prevents caption collisions at edges)
#   - Auto-fit: if content overflows, image size is reduced and layout is retried
#
# Deps:
#   pip install pillow pandas openpyxl

import os, re, sys, glob, math
from typing import Optional, List, Tuple
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

print(">>> Using Python interpreter:", sys.executable)

# --------------------------------------------------------------------
# Text (diacritics preserved)
# --------------------------------------------------------------------
TITLE_TEXT      = "Sri Parakala Matham Guru Parampara"
SUBTITLE_TEXT   = "Established by Sri Vedanta Desika in 1359 CE"
FOOTER_TEXT     = "Sri Parakala Matham – The Eternal Lineage of Sri Vedanta Desika"

# Section 2 heading (two lines: large main title + subtitle)
SECTION2_TITLE  = "Sri Parakāla Jeeyars"
SECTION2_SUB    = "Lineage of Brahmatantra Svatantra Swamis"

# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------
HERE        = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(HERE, "assets")
FONTS_DIR   = os.path.join(ASSETS_DIR, "fonts")
IMAGES_DIR  = os.path.join(HERE, "images")
XLSX_PATH   = os.path.join(HERE, "acharyan_captions.xlsx")

PARCHMENT_PATH    = os.path.join(ASSETS_DIR, "parchment_bg.jpg")
MANDALA_TILE_PATH = os.path.join(ASSETS_DIR, "mandala_tile.png")

OUT_A2 = os.path.join(HERE, "Sri_Parakala_Matham_Guru_Parampara_GRID_A2.png")

# --------------------------------------------------------------------
# Banner search (prefers images/Parakala Matham Banner.jpg)
# --------------------------------------------------------------------
def find_banner_path() -> Optional[str]:
    specific = os.path.join(IMAGES_DIR, "Parakala Matham Banner.jpg")
    if os.path.isfile(specific):
        return specific

    variants = [
        "Parakala Matham Banner.jpg", "Parakala_Matham_Banner.jpg",
        "Parakala Matham Banner.jpeg","Parakala_Matham_Banner.jpeg",
        "Parakala Matham Banner.png", "Parakala_Matham_Banner.png",
    ]
    for name in variants:
        p = os.path.join(IMAGES_DIR, name)
        if os.path.isfile(p):
            return p
    for name in variants:
        p = os.path.join(ASSETS_DIR, name)
        if os.path.isfile(p):
            return p
    for ext in ("*.jpg","*.jpeg","*.png"):
        for p in glob.glob(os.path.join(ASSETS_DIR, "**", ext), recursive=True):
            n = os.path.basename(p).lower()
            if "parakala" in n and "banner" in n:
                return p
    return None

# --------------------------------------------------------------------
# Font helpers (recursive search in assets/fonts/**)
# --------------------------------------------------------------------
_FONT_USED = None
_PRINTED_FONT = False

def _find_fonts_recursively(base_dir):
    if not os.path.isdir(base_dir):
        return []
    exts = ("*.ttf", "*.otf", "*.ttc")
    paths = []
    for ext in exts:
        paths.extend(glob.glob(os.path.join(base_dir, "**", ext), recursive=True))
    return paths

def _try_load_font(size: int, candidates: List[str]) -> Optional[ImageFont.FreeTypeFont]:
    global _FONT_USED
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                f = ImageFont.truetype(path, size=size)
                _FONT_USED = path
                return f
            except Exception:
                pass
    return None

def load_font(size: int) -> ImageFont.FreeTypeFont:
    preferred_names = [
        "GentiumPlus-Regular.ttf",
        "GentiumBookPlus-Regular.ttf",
        "NotoSerif-Regular.ttf",
        "DejaVuSerif.ttf",
    ]
    found = _find_fonts_recursively(FONTS_DIR)
    preferred = [p for name in preferred_names for p in found if os.path.basename(p).lower() == name.lower()]
    others    = [p for p in found if p not in preferred]
    f = _try_load_font(size, preferred + others)
    if f:
        return f

    system_candidates = [
        r"C:\Windows\Fonts\GentiumPlus-Regular.ttf",
        r"C:\Windows\Fonts\GentiumBookPlus-Regular.ttf",
        r"C:\Windows\Fonts\NotoSerif-Regular.ttf",
        r"C:\Windows\Fonts\DejaVuSerif.ttf",
        r"C:\Windows\Fonts\Cambria.ttc",
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\Nirmala.ttf",
        "/Library/Fonts/GentiumPlus-Regular.ttf",
        "/Library/Fonts/NotoSerif-Regular.ttf",
        "/Library/Fonts/Times New Roman.ttf",
        "/usr/share/fonts/truetype/gentiumplus/GentiumPlus-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]
    f = _try_load_font(size, system_candidates)
    if f:
        return f

    return ImageFont.load_default()

def print_font_choice_once():
    global _PRINTED_FONT
    if not _PRINTED_FONT:
        print(">>> Font used for text rendering:", _FONT_USED or "PIL default")
        _PRINTED_FONT = True

# --------------------------------------------------------------------
# Drawing utilities (Pillow 11 compatible)
# --------------------------------------------------------------------
def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def get_adaptive_colors(background_sample: Image.Image) -> Tuple[Tuple[int,int,int], Tuple[int,int,int]]:
    """
    Analyzes the background and returns a (text_color, shadow_color) pair for high contrast.
    """
    # Define color palettes
    dark_text = (101, 67, 33)    # A rich, deep gold/brown for high contrast on light backgrounds
    dark_shadow = (40, 25, 10)   # An even darker brown for a subtle, classic drop shadow
    light_text = (255, 245, 220) # Bright, creamy off-white
    light_shadow = (30, 20, 0)   # A dark shadow to give light text definition

    # Calculate average luminance using the standard (perceptual) formula
    stat = background_sample.convert("RGB").getdata()
    if not stat: return dark_text, dark_shadow # Default for empty samples
    avg_luma = sum(0.299*r + 0.587*g + 0.114*b for r,g,b in stat) / len(stat)

    # If background is bright (luma > 128 on a 0-255 scale), use dark text. Otherwise, use light text.
    if avg_luma > 128:
        return dark_text, light_shadow # Dark text on light background
    else:
        return light_text, dark_shadow # Light text on dark background

def draw_centered_text(img: Image.Image, text: str, y: int, size: int, color,
                       max_width: Optional[int] = None, line_gap: int = 10,
                       shadow_color: Optional[Tuple[int,int,int]] = None,
                       shadow_offset: Tuple[int,int] = (3,3)) -> int:
    if not text:
        return y
    d = ImageDraw.Draw(img)
    font = load_font(size)
    use_adaptive_color = color is None

    def _draw(x_pos, y_pos, txt, fill):
        d.text((x_pos, y_pos), txt, font=font, fill=fill)

    if max_width is None:
        w, h = _text_size(d, text, font)
        x = (img.width - w) // 2
        if use_adaptive_color:
            bg_sample = img.crop((x, y, x + w, y + h))
            color, shadow_color = get_adaptive_colors(bg_sample)

        if shadow_color:
            _draw(x + shadow_offset[0], y + shadow_offset[1], text, shadow_color)
        _draw(x, y, text, color)
        print_font_choice_once()
        return y + h

    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        tw, _ = _text_size(d, test, font)
        if tw <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    y0 = y
    for li in lines:
        lw, lh = _text_size(d, li, font)
        x = (img.width - lw)//2
        if use_adaptive_color:
            # Sample background for each line for maximum accuracy on gradients
            bg_sample = img.crop((x, y0, x + lw, y0 + lh))
            color, shadow_color = get_adaptive_colors(bg_sample)

        if shadow_color:
            _draw(x + shadow_offset[0], y0 + shadow_offset[1], li, shadow_color)
        _draw(x, y0, li, color)
        y0 += lh + line_gap
    print_font_choice_once()
    return y0

def tile_mandala_over(canvas: Image.Image, tile_path: str, opacity: int = 32):
    if not os.path.isfile(tile_path):
        return
    tile = Image.open(tile_path).convert("RGBA")
    alpha = tile.split()[-1].point(lambda a: int(a * (opacity / 255.0)))
    tile.putalpha(alpha)
    tw, th = tile.size
    for y in range(0, canvas.height, th):
        for x in range(0, canvas.width, tw):
            canvas.alpha_composite(tile, (x, y))

def draw_corner_overlays(canvas: Image.Image, assets_dir: str):
    """
    Draws a transparent overlay PNG onto the top-left and top-right corners.
    The right corner overlay is flipped horizontally for symmetry.
    """
    overlay_path = os.path.join(assets_dir, "overlay.png")
    if not os.path.isfile(overlay_path):
        # Silently skip if not found, as it's an optional decorative element.
        return

    try:
        overlay = Image.open(overlay_path).convert("RGBA")
    except Exception as e:
        print(f">>> Warning: Could not load 'overlay.png'. Error: {e}")
        return

    # Top-left corner
    canvas.alpha_composite(overlay, (0, 0))

    # Top-right corner (flipped horizontally)
    overlay_flipped = overlay.transpose(Image.FLIP_LEFT_RIGHT)
    canvas.alpha_composite(overlay_flipped, (canvas.width - overlay_flipped.width, 0))

def draw_banner(canvas: Image.Image, y: int, page_w: int, margin: int,
                max_height_fraction: float = 0.05,  # STRICT cap (5% of page height by default)
                feather_radius: int = 42,
                gold_tint_alpha: int = 44,
                desaturate: float = 1.0) -> int:
    """
    Draw the top banner, respecting its transparency.
    Returns y just after the banner. The banner height is strictly capped so the grid fits.
    """
    banner_path = find_banner_path()
    if not banner_path:
        print(">>> Banner not found (looked in images/ and assets/). Skipping banner.")
        return y

    banner = Image.open(banner_path).convert("RGBA")

    # --- STRICT scaling by BOTH width and height caps ---
    width_cap  = page_w - 2*margin
    height_cap = int(canvas.height * max_height_fraction)
    # Keep aspect ratio; respect both caps
    scale = min(width_cap / banner.width, height_cap / banner.height, 1.0)
    new_w = max(1, int(banner.width * scale))
    new_h = max(1, int(banner.height * scale))
    banner = banner.resize((new_w, new_h), Image.LANCZOS)
    # ----------------------------------------------------

    # Desaturate slightly to harmonize with parchment
    if desaturate != 1.0:
        conv = ImageEnhance.Color(banner)
        banner = conv.enhance(desaturate)

    # Composite centered using alpha channel
    x = (canvas.width - banner.width)//2
    canvas.alpha_composite(banner, (x, y))
    return y + banner.height + 20  # small spacing after banner

def draw_separator_block(canvas: Image.Image, y: int,
                         title_main: str, title_sub: str,
                         main_size: int, sub_size: int,
                         line_color=(212,175,55),
                         margin=80) -> int:
    d = ImageDraw.Draw(canvas)
    y_line = y + 12
    d.line((margin, y_line, canvas.width - margin, y_line), fill=line_color, width=3)
    y0 = y_line + 18
    y0 = draw_centered_text(canvas, title_main, y0, main_size, color=None,
                           shadow_offset=(4,4),
                           max_width=int(canvas.width*0.92), line_gap=8)
    y0 = draw_centered_text(canvas, title_sub, y0, sub_size, color=None,
                           shadow_offset=(3,3), max_width=int(canvas.width*0.92), line_gap=8)
    return y0 + 10

# --------------------------------------------------------------------
# Data utilities
# --------------------------------------------------------------------
def get_ordered_images(images_dir: str, pattern: str, group: int) -> List[str]:
    regex = re.compile(pattern, re.I)
    items = []
    for fn in os.listdir(images_dir):
        if not fn.lower().endswith(".png"):
            continue
        m = regex.match(fn)
        if not m:
            continue
        try:
            key = int(m.group(group))
        except Exception:
            continue
        items.append((key, os.path.join(images_dir, fn)))
    items.sort(key=lambda t: t[0])
    return [p for _, p in items]

def read_captions_from_xlsx(xlsx_path: str):
    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(f"XLSX not found: {xlsx_path}")
    df_f = pd.read_excel(xlsx_path, sheet_name="Founders_Early_Acharyas", engine="openpyxl")
    df_p = pd.read_excel(xlsx_path, sheet_name="acharyan_captions", engine="openpyxl")
    df_f.columns = [str(c).strip() for c in df_f.columns]
    df_p.columns = [str(c).strip() for c in df_p.columns]
    col_f = next(c for c in df_f.columns if "Founders" in c)
    col_p = next(c for c in df_p.columns if "Sri Parakāla" in c)
    cap_founders = df_f[col_f].dropna().astype(str).str.strip().tolist()
    cap_parakala = df_p[col_p].dropna().astype(str).str.strip().tolist()
    return cap_founders, cap_parakala

# --------------------------------------------------------------------
# Layout renderer (A2 only, 6 columns) with auto-fit retry
# --------------------------------------------------------------------
def render_once_A2(page_w: int, page_h: int, margin: int, num_cols: int,
                   gutter_x: int, row_gap: int, title_font: int, subtitle_font: int,
                   caption_font: int, footer_font: int, img_scale: float,
                   section_gap_extra: int, section2_title_size: int, section2_sub_size: int, 
                   banner_max_height_fraction: float,
                   parchment_brightness: float = 1.0, parchment_mode: str = 'tile',
                   featured_acharya_mode: bool = True) -> Tuple[Image.Image, int]:
    # Load captions + images (order only)
    cap_founders, cap_parakala = read_captions_from_xlsx(XLSX_PATH)
    img_founders = get_ordered_images(IMAGES_DIR, r"^F(\d{2}).*\.png$", 1)   # F01..F17 
    img_parakala = get_ordered_images(IMAGES_DIR, r"^(\d{4}).*\.png$", 1)    # 0100..3600

    founders_pairs: List[Tuple[str, str]] = []
    for i in range(max(len(cap_founders), len(img_founders))):
        caption = cap_founders[i] if i < len(cap_founders) else ""
        path    = img_founders[i] if i < len(img_founders) else ""
        founders_pairs.append((path, caption))

    parakala_pairs: List[Tuple[str, str]] = []
    for i in range(max(len(cap_parakala), len(img_parakala))):
        caption = cap_parakala[i] if i < len(cap_parakala) else ""
        path    = img_parakala[i] if i < len(img_parakala) else ""
        parakala_pairs.append((path, caption))

    # Background
    if os.path.isfile(PARCHMENT_PATH):
        if parchment_mode == 'stretch':
            parchment = Image.open(PARCHMENT_PATH).convert("RGB").resize((page_w, page_h), Image.LANCZOS)
        else: # 'tile' is the default
            parchment = Image.new("RGB", (page_w, page_h))
            tile_img = Image.open(PARCHMENT_PATH).convert("RGB")
            tw, th = tile_img.size
            for y in range(0, page_h, th):
                for x in range(0, page_w, tw):
                    parchment.paste(tile_img, (x, y))
        if parchment_brightness != 1.0:
            enhancer = ImageEnhance.Brightness(parchment)
            parchment = enhancer.enhance(parchment_brightness)
    else:
        parchment = Image.new("RGB", (page_w, page_h), (250, 240, 220))
    canvas = parchment.convert("RGBA")
    tile_mandala_over(canvas, MANDALA_TILE_PATH, opacity=32)
    draw_corner_overlays(canvas, ASSETS_DIR)
    d = ImageDraw.Draw(canvas)

    # Banner → Title → Subtitle
    y = margin
    y = draw_banner(canvas, y, page_w, margin,
                    max_height_fraction=banner_max_height_fraction,
                    feather_radius=44, gold_tint_alpha=48, desaturate=0.88)
    y = draw_centered_text(canvas, TITLE_TEXT, y, title_font, color=None, # color=None triggers adaptive mode
                           shadow_offset=(5, 5),
                           max_width=int(page_w*0.92), line_gap=12)
    y = draw_centered_text(canvas, SUBTITLE_TEXT, y + 8, subtitle_font, color=None,
                           shadow_offset=(3,3), max_width=int(page_w*0.92), line_gap=10)
    y += 24

    # --- Featured Acharya Mode ---
    if featured_acharya_mode and founders_pairs:
        featured_acharya = founders_pairs.pop(0)
        img_path, caption = featured_acharya

        # Draw the featured acharya, scaled to be prominent
        # The size of the featured image MUST also scale down during auto-fit attempts.
        featured_img_w = int(page_w * 0.25 * (img_scale / 0.68))
        featured_img_h = int(featured_img_w * 1.2)

        try:
            im = Image.open(img_path).convert("RGB")
        except Exception:
            im = Image.new("RGB", (featured_img_w, featured_img_h), (230,230,230))

        iw, ih = im.size
        scale = min(featured_img_w/iw, featured_img_h/ih)
        w, h = max(1, int(iw*scale)), max(1, int(ih*scale))
        im = im.resize((w,h), Image.LANCZOS)

        # Gold oval mask
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse([0,0,w-1,h-1], fill=255)
        im_oval = Image.new("RGBA", (w, h))
        im_oval.paste(im, (0,0), mask=mask)

        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=3)

        img_x = (page_w - w) // 2
        img_y = y + 20
        canvas.alpha_composite(stroke, (img_x-2, img_y-2))
        canvas.alpha_composite(im_oval, (img_x, img_y))

        y = img_y + h + 15

        # Draw caption for featured acharya
        cap_font = load_font(caption_font + 4) # Slightly larger caption font
        cap_w, cap_h = _text_size(d, caption, cap_font)
        bg_sample = canvas.crop(((page_w - cap_w)//2, y, (page_w + cap_w)//2, y + cap_h))
        cap_color, cap_shadow_color = get_adaptive_colors(bg_sample)

        tx = (page_w - cap_w) // 2
        d.text((tx + 2, y + 2), caption, font=cap_font, fill=cap_shadow_color)
        d.text((tx, y), caption, font=cap_font, fill=cap_color)

        y += cap_h + 40
    # --- End Featured Acharya Mode ---

    # Grid geometry
    total_gutter_width = (num_cols - 1) * gutter_x
    cell_w = (page_w - 2*margin - total_gutter_width) // num_cols
    x0 = margin

    def _text_size_local(d, text, font):
        bb = d.textbbox((0,0), text, font=font)
        return bb[2]-bb[0], bb[3]-bb[1]

    def draw_cell(x: int, y: int, img_path: str, caption: str) -> int:
        img_h_target = int(cell_w * img_scale)
        img_w_max    = cell_w
        try:
            im = Image.open(img_path).convert("RGB")
        except Exception:
            im = Image.new("RGB", (img_w_max, img_h_target), (230,230,230))
            dd = ImageDraw.Draw(im)
            dd.rectangle([0,0,im.width-1,im.height-1], outline=(120,120,120), width=2)
            dd.text((10,10), "Missing image", fill=(80,80,80))
        iw, ih = im.size
        scale = min(img_w_max/iw, img_h_target/ih)
        w, h = max(1, int(iw*scale)), max(1, int(ih*scale))
        im = im.resize((w,h), Image.LANCZOS)

        # gold oval mask
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse([0,0,w-1,h-1], fill=255)
        im_oval = Image.new("RGBA", (w, h))
        im_oval.paste(im, (0,0), mask=mask)

        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        sd = ImageDraw.Draw(stroke)
        sd.ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=2)

        img_x = x + (cell_w - w)//2
        img_y = y
        canvas.alpha_composite(stroke, (img_x-2, img_y-2))
        canvas.alpha_composite(im_oval, (img_x, img_y))

        # caption wrap
        cap_font = load_font(caption_font)
        d = ImageDraw.Draw(canvas)
        text = (caption or "").strip()
        words, lines, line = text.split(), [], ""
        max_text_w = cell_w - 6
        for tk in words:
            test = (line + " " + tk).strip()
            tw, _ = _text_size_local(d, test, cap_font)
            if tw <= max_text_w or not line:
                line = test
            else:
                lines.append(line); line = tk
        if line:
            lines.append(line)
        ty = img_y + h + 6

        # Adaptive color for captions
        total_text_h = sum(_text_size_local(d, li, cap_font)[1] for li in lines) + (len(lines) - 1) * 3
        if lines:
            max_lw = max(_text_size_local(d, li, cap_font)[0] for li in lines)
            bg_sample_x = x + (cell_w - max_lw) // 2
            bg_sample = canvas.crop((bg_sample_x, ty, bg_sample_x + max_lw, ty + total_text_h))
            cap_color, cap_shadow_color = get_adaptive_colors(bg_sample)
        else: # Default if no caption
            cap_color, cap_shadow_color = (70, 50, 0), (30, 20, 0)

        for li in lines:
            lw, lh = _text_size_local(d, li, cap_font)
            tx = x + (cell_w - lw)//2
            d.text((tx + 2, ty + 2), li, font=cap_font, fill=cap_shadow_color) # Subtle shadow
            d.text((tx, ty), li, font=cap_font, fill=cap_color)
            ty += lh + 3
        print_font_choice_once()
        return (ty - y)

    def draw_row(items: List[Tuple[str,str]], start_y: int) -> int:
        row_h = 0
        # Calculate horizontal offset for centering partial rows
        row_offset_x = 0
        if 0 < len(items) < num_cols:
            # Total width of the space occupied by the missing cells and their gutters
            unused_width = (num_cols - len(items)) * (cell_w + gutter_x)
            row_offset_x = unused_width // 2

        for col_idx, (p, cap) in enumerate(items):
            x = x0 + row_offset_x + col_idx * (cell_w + gutter_x)
            h_used = draw_cell(x, start_y, p, cap)
            if h_used > row_h:
                row_h = h_used
        return row_h

    # Section 1: Founders (17)
    idx = 0
    while idx < len(founders_pairs):
        slice_items = founders_pairs[idx: idx + num_cols]
        row_h = draw_row(slice_items, y)
        y += row_h + row_gap
        idx += num_cols

    # Bigger visual separation before section 2
    y += section_gap_extra
    y = draw_separator_block(canvas, y, SECTION2_TITLE, SECTION2_SUB,
                             main_size=section2_title_size, sub_size=section2_sub_size)
    y += section_gap_extra

    # Section 2: Parakala Jeeyars (36)
    idx = 0
    while idx < len(parakala_pairs):
        slice_items = parakala_pairs[idx: idx + num_cols]
        row_h = draw_row(slice_items, y)
        y += row_h + row_gap
        idx += num_cols

    # Footer (no border)
    footer_y = y + 24 # Use the actual y-position to check for overflow
    draw_centered_text(canvas, FOOTER_TEXT, footer_y, footer_font, color=None,
                       shadow_offset=(4,4),
                       max_width=int(page_w*0.92))

    return canvas.convert("RGB"), footer_y

def render_with_auto_fit(
        page_w: int = 4961, page_h: int = 7016,    # A2 ~300dpi
        margin: int = 90,
        num_cols: int = 6,
        gutter_x: int = 30,
        row_gap: int = 34,
        title_font: int = 170,
        subtitle_font: int = 60,
        caption_font: int = 40,
        footer_font: int = 46,
        img_scale: float = 0.68,
        section_gap_extra: int = 80,
        section2_title_size: int = 110,
        section2_sub_size: int = 58,
        banner_max_height_fraction: float = 0.05,   # 5% strict cap by default,
        parchment_brightness: float = 1.0,
        parchment_mode: str = 'tile',
        featured_acharya_mode: bool = True
    ) -> Optional[Image.Image]:
    """
    Renders once; if the layout overflows the page, auto-retries with slightly smaller images.
    Returns the final rendered image.
    """
    # Auto-fit by starting small and finding the largest scale that fits.
    best_img = None
    start_scale, end_scale, step = 0.40, 0.70, 0.01
    
    # Generate a list of scales to test, from small to large.
    scales_to_try = []
    current_scale = start_scale
    while current_scale <= end_scale:
        scales_to_try.append(round(current_scale, 2))
        current_scale += step

    print(f">>> Starting auto-fit process, testing scales from {start_scale} to {end_scale}...")
    for scale in scales_to_try:
        img, footer_y = render_once_A2(
            page_w, page_h, margin, num_cols, gutter_x, row_gap, title_font, subtitle_font,
            caption_font, footer_font, scale, section_gap_extra, section2_title_size,
            section2_sub_size, banner_max_height_fraction, parchment_brightness,
            parchment_mode, featured_acharya_mode)
        if footer_y <= page_h - 120: # Check if it fits with a safety margin
            print(f">>> Scale {scale:.2f} fits.")
            best_img = img # This scale is good, save the result
        else:
            print(f">>> Scale {scale:.2f} overflows. Using previous best fit.")
            break # This scale is too big, stop and use the last one that fit
    return best_img

# --------------------------------------------------------------------
# Main — A2 only
# --------------------------------------------------------------------
def main():
    final_image = render_with_auto_fit(
        page_w=4961, page_h=7016,   # A2 @ ~300dpi
        margin=90,
        num_cols=6,
        gutter_x=30,
        row_gap=34,
        title_font=170,
        subtitle_font=60,
        caption_font=40,
        footer_font=46,
        img_scale=0.68,
        section_gap_extra=80,
        section2_title_size=110,
        section2_sub_size=58, 
        banner_max_height_fraction=0.05,
        parchment_brightness=0.85,        # < 1.0 is darker, > 1.0 is brighter
        parchment_mode='stretch',         # Background mode. Options: 'tile' or 'stretch'.
        featured_acharya_mode=True        # If True, places the first founder centered at the top.
    )

    if final_image:
        # Save PNG
        final_image.save(OUT_A2, quality=95)
        print(f"Saved A2 poster as PNG → {OUT_A2}")
        # Save PDF
        pdf_path = OUT_A2.replace(".png", ".pdf")
        final_image.save(pdf_path, "PDF", resolution=300.0, quality=95)
        print(f"Saved A2 poster as PDF → {pdf_path}")

if __name__ == "__main__":
    main()
