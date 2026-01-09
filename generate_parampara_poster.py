# build_poster_from_xlsx.py
# A2 poster: Founders (F00 featured; F01..F17 in exactly 2 rows with contemporaries)
# + Parakāla Acharyas (IDs 1..36 mapped to image prefixes 0100..3600).
#
# This version:
#   - Footer is *always* at the page bottom (anchored), never on top of content
#   - Signature is drawn to the RIGHT of footer text on the same baseline
#   - Content is sized via binary search to fit above the footer band with a safety gap
#   - Shadows OFF by default; NumPy premultiply avoids Pillow ImageMath deprecations
#
# Deps: pip install pillow pandas openpyxl numpy

import os, re, sys, glob, math, unicodedata
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

print(">>> Python:", sys.executable)

# ---------- Text (M1-M5 defaults; overridden by Banner_Text in XLSX) ----------
DEFAULT_BANNER_MESSAGES = {
    "M1": "Sri Parakala Matham Guru Parampara",
    "M2": "Established by Sri Vedanta Desika in 1359 CE",
    "M3": "Sri Parakala Acharyas",
    "M4": "Lineage of Brahmatantra Swatantra Swamis",
    "M5": "Sri Parakala Swamy Mutt - The Eternal Lineage of Sri Vedanta Desika",
}

TITLE_TEXT      = DEFAULT_BANNER_MESSAGES["M1"]  # M1
SUBTITLE_TEXT   = DEFAULT_BANNER_MESSAGES["M2"]  # M2
SECTION2_TITLE  = DEFAULT_BANNER_MESSAGES["M3"]  # M3
SECTION2_SUB    = DEFAULT_BANNER_MESSAGES["M4"]  # M4
FOOTER_TEXT     = DEFAULT_BANNER_MESSAGES["M5"]  # M5

# Spacing tweaks to avoid header overlap across scripts
TITLE_SUBTITLE_GAP = 24
SECTION_TITLE_SUB_GAP = 10

# ---------- Style / Flags ----------
TITLE_FONT_WEIGHT    = "Bold"
SUBTITLE_FONT_WEIGHT = "Bold"
SECTION_FONT_WEIGHT  = "Bold"
FOOTER_FONT_WEIGHT   = "Bold"

# ---------- Shadow switches ----------
SHADOW_MODE = "none"        # "none" | "directional"
SHADOW_COLOR_HEX: Optional[str] = None  # None = adaptive
SHADOW_OPACITY   = 180
SHADOW_DIRECTION = "NW"  # NW, NE, SW, SE, CE
IMAGE_SHADOW_STRENGTH = 6
IMAGE_SHADOW_BLUR     = 8

MAGNIFY_FACTOR        = 1.50  # +10% for 'M' founders
FOUNDERS_ROWS         = 2
OVERLAY_CORNERS       = []
PARCHMENT_MODE        = "stretch"
PARCHMENT_BRIGHTNESS  = 0.85
FEATURED_ACHARYA_MODE = True  # F00 on top
SHOW_SIGNATURE        = True   # set False to suppress signature rendering
SIGNATURE_POSITION    = 6/8    # Horizontal position on footer line (0.0=left, 1.0=right). Default 6/8.

ALLOW_JPG_IMAGES      = True
IMG_EXTS              = (".png", ".jpg", ".jpeg") if ALLOW_JPG_IMAGES else (".png",)
RELAXED_MATCH_ANYWHERE = True  # match codes anywhere in filename

# ---------- Paths ----------
HERE        = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(HERE, "assets")
FONTS_DIR   = os.path.join(ASSETS_DIR, "fonts")
IMAGES_DIR  = os.path.join(HERE, "images")
DEFAULT_XLSX_CANDIDATES = [
    os.path.join(HERE, "acharyan_captiona_english.xlsx"),
    os.path.join(HERE, "acharyan_captions_english.xlsx"),
    os.path.join(HERE, "acharyan_captiona.xlsx"),
    os.path.join(HERE, "acharyan_captions.xlsx"),
]
XLSX_PATH   = next((p for p in DEFAULT_XLSX_CANDIDATES if os.path.isfile(p)), DEFAULT_XLSX_CANDIDATES[0])

PARCHMENT_PATH    = os.path.join(ASSETS_DIR, "parchment_bg.jpg")
MANDALA_TILE_PATH = os.path.join(ASSETS_DIR, "mandala_tile.png")
SIGNATURE_PATH    = os.path.join(ASSETS_DIR, "signature.png")
OUT_A2            = os.path.join(HERE, "Sri_Parakala_Matham_Guru_Parampara_GRID_A2.png")

# ---------- Fonts ----------
SELECTED_LANGUAGE = "english"

LANGUAGE_FONT_PREFS = {
    "english": {
        "normal": ["NotoSerif-VariableFont_wght.ttf","GentiumPlus-Regular.ttf","GentiumBookPlus-Regular.ttf","NotoSerif-Regular.ttf","DejaVuSerif.ttf"],
        "bold":   ["NotoSerif-VariableFont_wght.ttf","GentiumPlus-Bold.ttf","GentiumBookPlus-Bold.ttf","NotoSerif-Bold.ttf","DejaVuSerif-Bold.ttf"],
    },
    "kannada": {
        "normal": ["NotoSerifKannada-VariableFont_wght.ttf","NotoSerifKannada-Regular.ttf","NotoSansKannada-Regular.ttf","Tunga.ttf","Nirmala.ttf"],
        "bold":   ["NotoSerifKannada-VariableFont_wght.ttf","NotoSerifKannada-Bold.ttf","NotoSansKannada-Bold.ttf","Tunga.ttf","Nirmala.ttf"],
    },
    "telugu": {
        "normal": ["NotoSerifTelugu-VariableFont_wght.ttf","NotoSerifTelugu-Regular.ttf","NotoSansTelugu-Regular.ttf","Gautami.ttf","Nirmala.ttf"],
        "bold":   ["NotoSerifTelugu-VariableFont_wght.ttf","NotoSerifTelugu-Bold.ttf","NotoSansTelugu-Bold.ttf","Gautami.ttf","Nirmala.ttf"],
    },
    "tamil": {
        "normal": ["NotoSerifTamil-VariableFont_wght.ttf","NotoSerifTamil-Regular.ttf","NotoSansTamil-Regular.ttf","Latha.ttf","Nirmala.ttf"],
        "bold":   ["NotoSerifTamil-VariableFont_wght.ttf","NotoSerifTamil-Bold.ttf","NotoSansTamil-Bold.ttf","Latha.ttf","Nirmala.ttf"],
    },
    "sanskrit": {
        "normal": ["NotoSerifDevanagari-VariableFont_wght.ttf","NotoSerifDevanagari-Regular.ttf","NotoSansDevanagari-Regular.ttf","Nirmala.ttf","Mangal.ttf"],
        "bold":   ["NotoSerifDevanagari-VariableFont_wght.ttf","NotoSerifDevanagari-Bold.ttf","NotoSansDevanagari-Bold.ttf","Nirmala.ttf","Mangal.ttf"],
    },
}

_FONT_USED = None
_PRINTED_FONT = False
_FONT_CACHE: Dict[Tuple[int,str,str], ImageFont.FreeTypeFont] = {}

def _find_fonts_recursively(base_dir):
    if not os.path.isdir(base_dir): return []
    paths = []
    for ext in ("*.ttf","*.otf","*.ttc"):
        paths.extend(glob.glob(os.path.join(base_dir, "**", ext), recursive=True))
    return paths

def _try_load_font(size: int, candidates: List[str]) -> Optional[ImageFont.FreeTypeFont]:
    global _FONT_USED
    for path in candidates:
        if os.path.isfile(path):
            try:
                f = ImageFont.truetype(path, size=size)
                _FONT_USED = path
                return f
            except Exception:
                pass
    return None

def _apply_wght_variation_if_available(font: ImageFont.FreeTypeFont, weight: str) -> ImageFont.FreeTypeFont:
    """
    If the font is variable with a 'wght' axis, set it to 400/700 for normal/bold.
    Falls back silently if variation axes are unsupported.
    """
    try:
        getter = getattr(font, "get_variation_axes", None)
        setter = getattr(font, "set_variation_by_axes", None)
        if not getter or not setter:
            return font
        axes = getter() or []
        wght_idx = None
        values = []
        for idx, ax in enumerate(axes):
            tag = str(ax.get("tag") or ax.get("name") or "").lower()
            if tag == "wght":
                wght_idx = idx
            values.append(float(ax.get("defaultValue", ax.get("minValue", 0))))
        if wght_idx is None:
            return font
        lo = float(axes[wght_idx].get("minValue", 0))
        hi = float(axes[wght_idx].get("maxValue", 1000))
        target = 700.0 if weight.lower() == "bold" else 400.0
        values[wght_idx] = min(hi, max(lo, target))
        setter(values)
    except Exception:
        return font
    return font

def load_font(size: int, weight: str = 'normal') -> ImageFont.FreeTypeFont:
    lang = (SELECTED_LANGUAGE or "english").lower()
    key = (size, weight.lower(), lang)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    lang_map = LANGUAGE_FONT_PREFS.get(lang, LANGUAGE_FONT_PREFS["english"])
    pref_names = [n.lower() for n in lang_map.get(weight.lower(), lang_map.get('normal', []))]
    if not pref_names:
        pref_names = [n.lower() for n in LANGUAGE_FONT_PREFS["english"].get(weight.lower(), LANGUAGE_FONT_PREFS["english"]["normal"])]

    found = _find_fonts_recursively(FONTS_DIR)
    preferred = [p for p in found if os.path.basename(p).lower() in pref_names]
    preferred.sort(key=lambda p: pref_names.index(os.path.basename(p).lower()) if os.path.basename(p).lower() in pref_names else 999)
    others = [p for p in found if p not in preferred]
    f = _try_load_font(size, preferred + others)
    if not f:
        candidates = [
            # English / Latin
            r"C:\Windows\Fonts\GentiumPlus-Regular.ttf", r"C:\Windows\Fonts\GentiumPlus-Bold.ttf",
            r"C:\Windows\Fonts\NotoSerif-Regular.ttf",   r"C:\Windows\Fonts\NotoSerif-Bold.ttf",
            r"C:\Windows\Fonts\Cambria.ttc", r"C:\Windows\Fonts\times.ttf",
            # Indic families
            r"C:\Windows\Fonts\NotoSerifDevanagari-Regular.ttf", r"C:\Windows\Fonts\NotoSerifDevanagari-Bold.ttf",
            r"C:\Windows\Fonts\NotoSerifKannada-Regular.ttf",    r"C:\Windows\Fonts\NotoSerifKannada-Bold.ttf",
            r"C:\Windows\Fonts\NotoSerifTelugu-Regular.ttf",     r"C:\Windows\Fonts\NotoSerifTelugu-Bold.ttf",
            r"C:\Windows\Fonts\NotoSerifTamil-Regular.ttf",      r"C:\Windows\Fonts\NotoSerifTamil-Bold.ttf",
            r"C:\Windows\Fonts\NotoSansDevanagari-Regular.ttf",  r"C:\Windows\Fonts\NotoSansDevanagari-Bold.ttf",
            r"C:\Windows\Fonts\NotoSansKannada-Regular.ttf",     r"C:\Windows\Fonts\NotoSansKannada-Bold.ttf",
            r"C:\Windows\Fonts\NotoSansTelugu-Regular.ttf",      r"C:\Windows\Fonts\NotoSansTelugu-Bold.ttf",
            r"C:\Windows\Fonts\NotoSansTamil-Regular.ttf",       r"C:\Windows\Fonts\NotoSansTamil-Bold.ttf",
            r"C:\Windows\Fonts\Tunga.ttf", r"C:\Windows\Fonts\Gautami.ttf", r"C:\Windows\Fonts\Latha.ttf",
            r"C:\Windows\Fonts\Mangal.ttf", r"C:\Windows\Fonts\Nirmala.ttf",
            "/Library/Fonts/GentiumPlus-Regular.ttf", "/Library/Fonts/GentiumPlus-Bold.ttf",
            "/Library/Fonts/NotoSerif-Regular.ttf",   "/Library/Fonts/NotoSerif-Bold.ttf",
            "/Library/Fonts/NotoSerifDevanagari-Regular.ttf", "/Library/Fonts/NotoSerifDevanagari-Bold.ttf",
            "/Library/Fonts/NotoSerifTamil-Regular.ttf", "/Library/Fonts/NotoSerifTamil-Bold.ttf",
            "/usr/share/fonts/truetype/gentiumplus/GentiumPlus-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifTamil-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]
        f = _try_load_font(size, candidates) or ImageFont.load_default()
    f = _apply_wght_variation_if_available(f, weight)
    _FONT_CACHE[key] = f
    return f

def print_font_choice_once():
    global _PRINTED_FONT
    if not _PRINTED_FONT:
        print(">>> Font:", _FONT_USED or "PIL default")
        _PRINTED_FONT = True

# ---------- Drawing helpers ----------
def _text_size(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bb = d.textbbox((0,0), text, font=font)
    return bb[2]-bb[0], bb[3]-bb[1]

def wrap_text_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Word-wrap with a fallback to character splits if a single word exceeds max_width."""
    if max_width <= 0:
        return [text] if text else []
    dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
    def split_long_word(word: str) -> List[str]:
        parts=[]; cur=""
        for ch in word:
            test = cur + ch
            w,_ = _text_size(dummy, test, font)
            if w <= max_width:
                cur = test
            else:
                if cur:
                    parts.append(cur)
                    cur = ch
                else:
                    parts.append(ch)  # single glyph too wide; force break
        if cur: parts.append(cur)
        return parts

    words = text.split()
    if not words:
        return []
    lines=[]
    line=""
    for word in words:
        candidate = (line + " " + word).strip() if line else word
        w,_ = _text_size(dummy, candidate, font)
        if w <= max_width:
            line = candidate
            continue
        # current line can't fit the new word; push current if exists
        if line:
            lines.append(line)
            line = ""
        # word itself too long? split it
        chunks = split_long_word(word)
        for chunk in chunks:
            w_chunk,_ = _text_size(dummy, chunk, font)
            if not line:
                line = chunk
            elif _text_size(dummy, (line + " " + chunk).strip(), font)[0] <= max_width:
                line = (line + " " + chunk).strip()
            else:
                lines.append(line)
                line = chunk
    if line:
        lines.append(line)
    return lines

def _hex_to_rgb(h: str) -> Tuple[int,int,int]:
    h = h.lstrip('#'); return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

def get_shadow_offset(off: int):
    m = SHADOW_DIRECTION.upper()
    return {"NW":( off,  off), "NE":(-off,  off), "SW":( off, -off), "SE":(-off, -off), "CE":(0,0)}.get(m,(0,0))

def get_adaptive_colors(bg: Image.Image):
    sm = bg.resize((16,16), Image.BILINEAR).convert("RGB")
    px = list(sm.getdata())
    luma = sum(0.299*r + 0.587*g + 0.114*b for r,g,b in px)/len(px)
    dark_text   = (101,67,33)
    light_text  = (255,245,220)
    dark_shadow = (30,20,0)
    light_shadow= (40,25,10)
    return (dark_text,dark_shadow) if luma>128 else (light_text,light_shadow)

def draw_centered_text(img, text, y, size, color=None, max_width=None, line_gap=10, shadow_strength=3, font_weight='normal'):
    if not text: return y
    d = ImageDraw.Draw(img)
    font = load_font(size, font_weight)
    s_off = get_shadow_offset(shadow_strength)
    s_override = None
    if SHADOW_COLOR_HEX:
        s_override = (*_hex_to_rgb(SHADOW_COLOR_HEX), SHADOW_OPACITY)

    def draw_line(line, y0):
        lw, lh = _text_size(d, line, font)
        x = (img.width - lw)//2
        fg, sh = (color, (40,25,10)) if color is not None else get_adaptive_colors(img.crop((x,y0,x+lw,y0+lh)))
        if s_override: sh = s_override
        if shadow_strength>0:
            d.text((x+s_off[0], y0+s_off[1]), line, font=font, fill=sh)
        d.text((x, y0), line, font=font, fill=fg)
        return y0 + lh

    if max_width is None:
        y = draw_line(text, y)
        print_font_choice_once()
        return y

    words = text.split(); lines=[]; line=""
    for w in words:
        t=(line+" "+w).strip(); tw,_=_text_size(d,t,font)
        if tw<=max_width or not line: line=t
        else: lines.append(line); line=w
    if line: lines.append(line)
    for li in lines:
        y = draw_line(li, y) + line_gap
    print_font_choice_once()
    return y

def tile_mandala_over(canvas, tile_path, opacity=32):
    if not os.path.isfile(tile_path): return
    tile = Image.open(tile_path).convert("RGBA")
    a = tile.split()[-1].point(lambda v: int(v*(opacity/255.0))); tile.putalpha(a)
    tw,th = tile.size
    for yy in range(0, canvas.height, th):
        for xx in range(0, canvas.width, tw):
            canvas.alpha_composite(tile, (xx,yy))

def find_banner_path() -> Optional[str]:
    prefer = [
        os.path.join(IMAGES_DIR, "Parakala Matham Banner.png"),
        os.path.join(IMAGES_DIR, "Parakala_Matham_Banner.png"),
        os.path.join(IMAGES_DIR, "Parakala Matham Banner.jpg"),
        os.path.join(IMAGES_DIR, "Parakala_Matham_Banner.jpg"),
    ]
    for p in prefer:
        if os.path.isfile(p): return p
    for ext in ("*.jpg","*.jpeg","*.png"):
        for p in glob.glob(os.path.join(ASSETS_DIR,"**",ext), recursive=True):
            n=os.path.basename(p).lower()
            if "parakala" in n and "banner" in n: return p
    return None

def draw_banner(canvas, y, page_w, margin, max_height_fraction=0.05):
    path = find_banner_path()
    if not path: return y
    b = Image.open(path).convert("RGBA")
    width_cap  = page_w - 2*margin
    height_cap = int(canvas.height*max_height_fraction)
    s = min(width_cap/b.width, height_cap/b.height, 1.0)
    if s < 1.0:
        new_w, new_h = max(1, int(b.width*s)), max(1, int(b.height*s))
        b = b.resize((new_w,new_h), Image.LANCZOS)
    new_w, new_h = b.size

    if SHADOW_MODE == "directional" and IMAGE_SHADOW_STRENGTH>0 and IMAGE_SHADOW_BLUR>0:
        mask = b.getchannel('A')
        sh_col = (40,25,10,150) if not SHADOW_COLOR_HEX else (*_hex_to_rgb(SHADOW_COLOR_HEX), SHADOW_OPACITY)
        sh = Image.new("RGBA", b.size, sh_col); sh.putalpha(mask)
        sh = sh.filter(ImageFilter.GaussianBlur(radius=IMAGE_SHADOW_BLUR))
        off = get_shadow_offset(IMAGE_SHADOW_STRENGTH)
        sx = (canvas.width-new_w)//2 + off[0]; sy = y + off[1]
        canvas.alpha_composite(sh,(sx,sy))

    x = (canvas.width-new_w)//2
    canvas.alpha_composite(b, (x,y))
    return y + new_h + 20

# ---------- Alpha-safe image helpers ----------
def open_rgba(path: str) -> Image.Image:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        im = Image.new("RGBA", (400, 400), (230,230,230,255))
        d  = ImageDraw.Draw(im)
        d.rectangle([0,0,399,399], outline=(120,120,120,255), width=2)
        d.text((10,10), "Missing image", fill=(80,80,80,255))
        return im

def resize_rgba_premultiplied(im: Image.Image, new_w: int, new_h: int) -> Image.Image:
    if im.mode != "RGBA": im = im.convert("RGBA")
    im_np = np.array(im, dtype=np.uint8)
    rgb = im_np[..., :3].astype(np.float32)
    a   = im_np[..., 3:4].astype(np.float32)
    rgb_p = (rgb * (a / 255.0))
    premul_img = Image.fromarray(np.clip(np.concatenate([rgb_p, a], axis=-1), 0, 255).astype(np.uint8), "RGBA")
    pm_resized = premul_img.resize((new_w, new_h), Image.LANCZOS)
    pm_np = np.array(pm_resized, dtype=np.uint8).astype(np.float32)
    rgb_p2 = pm_np[..., :3]; a2 = pm_np[..., 3:4]
    denom = np.maximum(a2, 1.0)
    rgb_u = 255.0 * (rgb_p2 / denom)
    out = np.concatenate([np.clip(rgb_u, 0, 255), a2], axis=-1).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def make_circular(im: Image.Image, out_w: int, out_h: int) -> Tuple[Image.Image, Image.Image, Image.Image]:
    if im.mode != "RGBA": im = im.convert("RGBA")
    iw, ih = im.size
    scale = min(out_w/iw, out_h/ih)
    w = max(1, int(iw*scale)); h = max(1, int(ih*scale))
    im = resize_rgba_premultiplied(im, w, h)
    _, _, _, a = im.split()
    circle_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(circle_mask).ellipse([0,0,w-1,h-1], fill=255)
    combined_mask = ImageChops.multiply(a, circle_mask)
    im.putalpha(combined_mask)
    return im, combined_mask, circle_mask

def shadow_from_mask(mask: Image.Image, color=(40,25,10,150), blur=8) -> Image.Image:
    sh = Image.new("RGBA", mask.size, color); sh.putalpha(mask)
    if blur > 0: sh = sh.filter(ImageFilter.GaussianBlur(radius=blur))
    return sh

def maybe_draw_shadow(canvas: Image.Image, mask_for_shadow: Image.Image, dest_xy: Tuple[int,int]):
    if SHADOW_MODE != "directional": return
    sh_col = (40,25,10,150) if not SHADOW_COLOR_HEX else (*_hex_to_rgb(SHADOW_COLOR_HEX), SHADOW_OPACITY)
    sh = shadow_from_mask(mask_for_shadow, color=sh_col, blur=IMAGE_SHADOW_BLUR)
    off = get_shadow_offset(IMAGE_SHADOW_STRENGTH)
    canvas.alpha_composite(sh, (dest_xy[0] + off[0], dest_xy[1] + off[1]))

def normalize_ascii_lower(text: Optional[str]) -> str:
    """Lowercase helper that strips diacritics for reliable header detection."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.lower()

# ---------- Language + banner helpers ----------
LANGUAGE_ALIASES = {
    "": "english",
    "english": "english",
    "en": "english",
    "kannada": "kannada",
    "kn": "kannada",
    "telugu": "telugu",
    "te": "telugu",
    "tamil": "tamil",
    "ta": "tamil",
    "sanskrit": "sanskrit",
    "sa": "sanskrit",
}

def resolve_language_choice(raw: str) -> str:
    key = normalize_ascii_lower(raw or "").replace(" ", "")
    return LANGUAGE_ALIASES.get(key, "english")

def resolve_xlsx_path(language_choice: str) -> str:
    lang = normalize_ascii_lower(language_choice).replace(" ", "")
    candidates = [
        os.path.join(HERE, f"acharyan_captiona_{lang}.xlsx"),
        os.path.join(HERE, f"acharyan_captions_{lang}.xlsx"),
    ]
    if lang == "english":
        candidates += DEFAULT_XLSX_CANDIDATES
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"No spreadsheet found for language '{language_choice}'. Tried: {candidates}"
    )

def load_banner_messages(xlsx_path: str, defaults: Dict[str,str]) -> Dict[str,str]:
    messages = dict(defaults)
    try:
        df = pd.read_excel(xlsx_path, sheet_name="Banner_Text", engine="openpyxl")
    except Exception as e:
        print(f">>> WARNING: Banner_Text missing or unreadable in {xlsx_path}: {e}")
        return messages

    # Detect columns by header names (accent/space-insensitive)
    id_col = None
    msg_col = None
    for col in df.columns:
        norm = normalize_ascii_lower(col).replace(" ", "")
        if id_col is None and (norm.startswith("messageid") or norm == "id"):
            id_col = col
            continue
        if msg_col is None and (norm == "message" or norm == "text" or (norm.startswith("message") and not norm.startswith("messageid"))):
            msg_col = col
    if id_col is None or msg_col is None:
        print(f">>> WARNING: Banner_Text sheet missing 'Message ID'/'Message' headers in {xlsx_path}")
        return messages

    for _, row in df.iterrows():
        mid_raw = row.get(id_col)
        msg_raw = row.get(msg_col)
        if pd.isna(mid_raw) or pd.isna(msg_raw):
            continue
        mid = str(mid_raw).strip().upper()
        msg = str(msg_raw).strip()
        if not mid or not msg:
            continue
        if mid in messages:
            messages[mid] = msg
    return messages

def apply_banner_messages(messages: Dict[str,str]):
    global TITLE_TEXT, SUBTITLE_TEXT, SECTION2_TITLE, SECTION2_SUB, FOOTER_TEXT
    TITLE_TEXT     = messages.get("M1", DEFAULT_BANNER_MESSAGES["M1"])
    SUBTITLE_TEXT  = messages.get("M2", DEFAULT_BANNER_MESSAGES["M2"])
    SECTION2_TITLE = messages.get("M3", DEFAULT_BANNER_MESSAGES["M3"])
    SECTION2_SUB   = messages.get("M4", DEFAULT_BANNER_MESSAGES["M4"])
    FOOTER_TEXT    = messages.get("M5", DEFAULT_BANNER_MESSAGES["M5"])

# ---------- Data ----------
def read_xlsx(xlsx_path: Optional[str] = None):
    xlsx_file = xlsx_path or XLSX_PATH
    if not os.path.isfile(xlsx_file):
        raise FileNotFoundError(f"Data file not found: {xlsx_file}")

    def pick_sheet(xl: pd.ExcelFile, candidates: List[str]) -> str:
        """Pick the first matching sheet (case-insensitive, underscores/spaces ignored)."""
        available = xl.sheet_names
        norm_map = {}
        for s in available:
            key = s.replace("_", "").replace(" ", "").lower()
            norm_map[key] = s
        for cand in candidates:
            key = cand.replace("_", "").replace(" ", "").lower()
            if key in norm_map:
                return norm_map[key]
        # fallback to the first sheet
        return available[0]

    xl = pd.ExcelFile(xlsx_file, engine="openpyxl")
    founders_sheet = pick_sheet(xl, ["Founders_Early_Acharyas", "Earlier_Acharyas", "Founders"])
    parakala_sheet = pick_sheet(xl, ["acharyan_captions", "PLM acharyas", "Parakala", "PLM_acharyas"])
    df_f = xl.parse(sheet_name=founders_sheet, header=None)
    df_p = xl.parse(sheet_name=parakala_sheet, header=None)

    # Drop spacer columns that are entirely blank so indexes stay consistent
    df_f = df_f.dropna(axis=1, how='all')
    df_p = df_p.dropna(axis=1, how='all')

    def _is_numeric(col, sample_size=12):
        try:
            sample = pd.to_numeric(col.dropna().astype(str).str.strip().head(sample_size), errors="coerce")
            return sample.notna().mean() > 0.8
        except Exception:
            return False

    # Heuristically detect founder columns (handles layouts where ID and caption swap columns)
    id_col = 0
    caption_col = 1 if df_f.shape[1] > 1 else 0
    group_col = 2 if df_f.shape[1] > 2 else None
    enhance_col = 3 if df_f.shape[1] > 3 else None

    # Prefer column containing F-codes for IDs
    fcode_cols = []
    for c in range(df_f.shape[1]):
        vals = df_f.iloc[:, c].dropna().astype(str).str.strip()
        if vals.empty: continue
        score = vals.head(12).str.match(r'^[Ff]\d+').mean()
        if score > 0.5:
            fcode_cols.append(c)
    if fcode_cols:
        id_col = fcode_cols[0]

    # Choose caption column as the first non-ID, mostly non-numeric column with longest text
    caption_candidates = []
    for c in range(df_f.shape[1]):
        if c == id_col: continue
        vals = df_f.iloc[:, c].dropna().astype(str).str.strip()
        if vals.empty: continue
        num_ratio = _is_numeric(vals)
        avg_len = vals.head(12).map(len).mean() if not vals.empty else 0
        caption_candidates.append((num_ratio, -avg_len, c))
    if caption_candidates:
        caption_candidates.sort()
        caption_col = caption_candidates[0][2]

    # Group column: first non-ID/non-caption column that is mostly numeric
    for c in range(df_f.shape[1]):
        if c in (id_col, caption_col): continue
        if _is_numeric(df_f.iloc[:, c]):
            group_col = c
            break

    # Enhance column: any column with an 'M' flag
    for c in range(df_f.shape[1]):
        if c in (id_col, caption_col, group_col): continue
        vals = df_f.iloc[:, c].dropna().astype(str).str.strip().str.upper().head(20)
        if any(v == 'M' for v in vals):
            enhance_col = c
            break

    # Founders: optional header skip (accent-insensitive)
    first_val_f = ""
    first_id_f = ""
    try:
        first_val_f = normalize_ascii_lower(df_f.iloc[0,caption_col])
        first_id_f = normalize_ascii_lower(df_f.iloc[0,id_col])
    except Exception:
        pass
    header_markers = ("acharya","acharyas","founder","founders","caption","name","lineage")
    id_markers = ("sl no","slno","id","no","s.no")
    if any(k in first_val_f for k in header_markers) or any(first_id_f.startswith(k) for k in id_markers):
        df_f = df_f.iloc[1:].reset_index(drop=True)

    founders = []
    for i,row in df_f.iterrows():
        if len(row)<2: continue
        try:
            id_raw = row.iloc[id_col] if id_col < len(row) else None
            if pd.isna(id_raw):
                raise ValueError("Missing founder ID")
            id_val = str(id_raw).strip()
            if id_val.upper().startswith('F'):
                fid = int(id_val[1:])
            else:
                fid = int(float(id_val))

            cap_raw = row.iloc[caption_col] if caption_col < len(row) else None
            cap = "" if pd.isna(cap_raw) else str(cap_raw).strip()

            grp_raw = row.iloc[group_col] if group_col is not None and group_col < len(row) else None
            if pd.notna(grp_raw):
                try:
                    grp = int(float(str(grp_raw).strip()))
                except Exception:
                    grp = str(grp_raw).strip() or f"unique_{i}"
            else:
                grp = f"unique_{i}"

            is_m = False
            if enhance_col is not None and enhance_col < len(row):
                enh_raw = row.iloc[enhance_col]
                if pd.notna(enh_raw):
                    is_m = str(enh_raw).strip().upper()=='M'
            founders.append({"id": fid, "caption": cap, "group_id": grp, "is_main": is_m})
        except Exception as e:
            print(f">>> WARNING: Skipping founder row {i} due to error: {e} (Row data: {row.to_list()})")
            continue

    # Parak??la: optional header skip
    try: first_val_p = normalize_ascii_lower(df_p.iloc[0,0])
    except Exception: first_val_p = ""
    try: first_cap_p = normalize_ascii_lower(df_p.iloc[0,1])
    except Exception: first_cap_p = ""
    if any(k in first_val_p for k in ("sl no","slno","id","no","s.no")) or any(k in first_cap_p for k in ("acharya","acharyas","mutt","matha","parakala")):
        df_p = df_p.iloc[1:].reset_index(drop=True)

    parakala = []
    for _,row in df_p.iterrows():
        if len(row)<2: continue
        try:
            pid = int(float(row.iloc[0]))              # 1..36 (Excel)
            cap = str(row.iloc[1]).strip()
            if cap:
                parakala.append({"id": pid, "caption": cap})
        except Exception:
            continue
    return founders, parakala

# ---------- Image indexing ----------
def index_images(images_dir: str):
    founders_map: Dict[str,str] = {}
    parakala_map: Dict[str,str] = {}

    re_f_any = re.compile(r'[fF](\d{2})') if RELAXED_MATCH_ANYWHERE else re.compile(r'^[fF](\d{2})')
    re_p_any = re.compile(r'(\d{4})')     if RELAXED_MATCH_ANYWHERE else re.compile(r'^(\d{4})')

    files = os.listdir(images_dir)
    if not files:
        print(f">>> WARNING: images folder is empty: {images_dir}")

    for fn in files:
        fn_low = fn.lower()
        if not fn_low.endswith(IMG_EXTS): continue
        full = os.path.join(images_dir, fn)

        m_f = re_f_any.search(fn)
        if m_f:
            founders_map[f"f{m_f.group(1)}".lower()] = full
            continue

        m_p = re_p_any.search(fn)
        if m_p and len(m_p.group(1)) == 4:
            parakala_map[m_p.group(1)] = full
            continue

    print(f">>> Indexed founders images: {len(founders_map)}")
    print(f">>> Indexed Parakāla images: {len(parakala_map)}")
    return founders_map, parakala_map

# ---------- Separator ----------
def draw_separator_block(canvas, y, title_main, title_sub, main_size, sub_size, line_color=(212,175,55), margin=80):
    d = ImageDraw.Draw(canvas)
    y_line=y+12
    d.line((margin,y_line, canvas.width-margin, y_line), fill=line_color, width=3)
    y0 = y_line+18
    y0 = draw_centered_text(canvas, title_main, y0, main_size, color=None,
                            shadow_strength=4, font_weight=SECTION_FONT_WEIGHT,
                            max_width=int(canvas.width*0.92), line_gap=8)
    y0 += SECTION_TITLE_SUB_GAP
    y0 = draw_centered_text(canvas, title_sub,  y0, sub_size,  color=None,
                            shadow_strength=3, font_weight=SECTION_FONT_WEIGHT,
                            max_width=int(canvas.width*0.92), line_gap=8)
    return y0 + 10

# ---------- Content render (returns canvas + content_end_y) ----------
def render_content(page_w:int, page_h:int, margin:int, num_cols:int, gutter_x:int, row_gap:int,
                   title_font:int, subtitle_font:int, caption_font:int,
                   img_scale:float, section_gap_extra:int, section2_title_size:int, section2_sub_size:int,
                   banner_max_height_fraction:float, parchment_brightness:float=1.0,
                   parchment_mode:str='stretch', featured_acharya_mode:bool=True,
                   founders_data: Optional[List[dict]] = None, parakala_data: Optional[List[dict]] = None,
                   founders_map: Optional[Dict[str,str]] = None, parakala_map: Optional[Dict[str,str]] = None,
                   xlsx_path: Optional[str] = None
                   ) -> Tuple[Image.Image, int]:
    if founders_data is None or parakala_data is None:
        founders_data, parakala_data = read_xlsx(xlsx_path)
    if founders_map is None or parakala_map is None:
        founders_map, parakala_map = index_images(IMAGES_DIR)
    f_map, p_map = founders_map, parakala_map

    # Background
    if os.path.isfile(PARCHMENT_PATH):
        if PARCHMENT_MODE=='stretch':
            parchment = Image.open(PARCHMENT_PATH).convert("RGB").resize((page_w,page_h), Image.LANCZOS)
        else:
            src = Image.open(PARCHMENT_PATH).convert("RGB")
            parchment = Image.new("RGB",(page_w,page_h))
            tw,th = src.size
            for yy in range(0,page_h,th):
                for xx in range(0,page_w,tw):
                    parchment.paste(src,(xx,yy))
        if PARCHMENT_BRIGHTNESS!=1.0:
            parchment = ImageEnhance.Brightness(parchment).enhance(PARCHMENT_BRIGHTNESS)
    else:
        parchment = Image.new("RGB",(page_w,page_h),(250,240,220))
    canvas = parchment.convert("RGBA")
    tile_mandala_over(canvas, MANDALA_TILE_PATH, opacity=32)
    d = ImageDraw.Draw(canvas)

    # Banner / Title / Subtitle
    y = margin
    y = draw_banner(canvas, y, page_w, margin, max_height_fraction=banner_max_height_fraction)
    y = draw_centered_text(canvas, TITLE_TEXT, y, title_font, color=None, shadow_strength=5,
                           font_weight=TITLE_FONT_WEIGHT, max_width=int(page_w*0.92), line_gap=12)
    y = draw_centered_text(canvas, SUBTITLE_TEXT, y+TITLE_SUBTITLE_GAP, subtitle_font, color=None, shadow_strength=3,
                           font_weight=SUBTITLE_FONT_WEIGHT, max_width=int(page_w*0.92), line_gap=10)
    y += 22

    # Map founders
    featured = None
    grouped_plain: Dict[str, List[dict]] = {}
    for it in founders_data:
        fid = it['id']
        key = f"f{fid:02d}"
        path = f_map.get(key, "")
        if fid == 0 and featured_acharya_mode:
            featured = {**it, "path": path}
        else:
            gid = str(it['group_id'])
            grouped_plain.setdefault(gid, []).append({**it, "path": path})

    # Featured F00
    if featured:
        img_w_max = int(page_w*0.22)
        img_h_tgt = int(img_w_max*img_scale*1.2)
        im = open_rgba(featured["path"])
        iw, ih = im.size
        s = min(img_w_max/iw, img_h_tgt/ih)
        w, h = max(1,int(iw*s)), max(1,int(ih*s))
        im_circ, comb_mask, circle_mask = make_circular(im, w, h)
        x_center = (page_w - w)//2
        maybe_draw_shadow(canvas, circle_mask, (x_center, y))
        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=3)
        canvas.alpha_composite(stroke,(x_center-2,y-2))
        canvas.alpha_composite(im_circ,(x_center,y))
        # caption
        y2 = y + h + 12
        cap_font = load_font(caption_font)
        max_text_w = int(page_w * 0.6)
        lines = wrap_text_to_width(featured["caption"], cap_font, max_text_w)
        if lines:
            max_lw = max(_text_size(d, li, cap_font)[0] for li in lines)
            total_h = sum(_text_size(d, li, cap_font)[1] for li in lines) + (len(lines)-1)*4
            bg = canvas.crop(((page_w-max_lw)//2, y2, (page_w+max_lw)//2, y2+total_h))
            fg, sh_color_base = get_adaptive_colors(bg)
        else:
            total_h = 0
            fg, sh_color_base = (70,50,0),(30,20,0)
        s_off = get_shadow_offset(2)
        ty = y2
        for li in lines:
            lw, lh = _text_size(d, li, cap_font)
            tx = (page_w - lw)//2
            d.text((tx+s_off[0], ty+s_off[1]), li, font=cap_font, fill=sh_color_base)
            d.text((tx,          ty          ), li, font=cap_font, fill=fg)
            ty += lh + 4
        y = y2 + total_h + 28

    # Founders in 2 rows; contemporaries stacked within columns
    ordered_groups: List[List[dict]] = []
    seen=set()
    for it in sum(grouped_plain.values(), []):
        gid = str(it['group_id'])
        if gid in seen: continue
        ordered_groups.append(grouped_plain[gid]); seen.add(gid)
    total_groups = len(ordered_groups)
    rows_groups = [[],[]]
    if total_groups>0:
        row1_count = math.ceil(total_groups/2)
        rows_groups = [ordered_groups[:row1_count], ordered_groups[row1_count:]]

    # Determine max columns to standardize cell width across rows
    max_cols_in_founder_rows = max(len(rg) for rg in rows_groups) if rows_groups and any(rows_groups) else 1

    def draw_group_row(row_groups: List[List[dict]], start_y: int, max_cols: int) -> int:
        if not row_groups: return 0
        cols = len(row_groups)
        total_gutter_for_max = (max_cols-1)*gutter_x
        cell_w = (page_w - 2*margin - total_gutter_for_max)//max(1,max_cols)

        def draw_cell(x:int, y0:int, img_path:str, caption:str, magnification:float=1.0, measure_only:bool=False) -> int:
            img_w_max = int(cell_w * magnification)
            img_h_tgt = int(img_w_max * img_scale)
            im_src = open_rgba(img_path)
            iw, ih = im_src.size
            s = min(img_w_max/iw, img_h_tgt/ih)
            w, h = max(1,int(iw*s)), max(1,int(ih*s))
            im_circ, comb_mask, circle_mask = make_circular(im_src, w, h)

            if not measure_only:
                ix = x + (cell_w - w)//2
                maybe_draw_shadow(canvas, circle_mask, (ix, y0))
                stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
                ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=2)
                canvas.alpha_composite(stroke,(ix-2,y0-2))
                canvas.alpha_composite(im_circ,(ix,y0))

            cap_font = load_font(caption_font)
            max_text_w = int(cell_w * 0.9)
            measurer = ImageDraw.Draw(Image.new("RGBA",(1,1))) if measure_only else ImageDraw.Draw(canvas)
            lines = wrap_text_to_width(caption, cap_font, max_text_w)
            ty = y0 + h + 6
            if measure_only:
                total_h = sum(_text_size(measurer, li, cap_font)[1] for li in lines) + (len(lines)-1)*4
                return (ty - y0) + total_h
            if lines:
                max_lw = max(_text_size(measurer, li, cap_font)[0] for li in lines)
                total_h = sum(_text_size(measurer, li, cap_font)[1] for li in lines) + (len(lines)-1)*4
                bg = canvas.crop((x+(cell_w-max_lw)//2, ty, x+(cell_w-max_lw)//2+max_lw, ty+total_h))
                fg, sh_color_base = get_adaptive_colors(bg)
            else:
                fg, sh_color_base = (70,50,0),(30,20,0)
            s_off = get_shadow_offset(2)
            for li in lines:
                lw,lh=_text_size(measurer, li, cap_font); tx=x+(cell_w-lw)//2
                ImageDraw.Draw(canvas).text((tx+s_off[0], ty+s_off[1]), li, font=cap_font, fill=sh_color_base)
                ImageDraw.Draw(canvas).text((tx,          ty          ), li, font=cap_font, fill=fg)
                ty += lh + 4
            print_font_choice_once()
            return ty - y0

        # measure
        col_heights=[]
        for grp in row_groups:
            acc=0
            for item in grp:
                magn = MAGNIFY_FACTOR if item.get("is_main") else 1.0
                path = f_map.get(f"f{item['id']:02d}", "")
                acc += draw_cell(0,0,path, item["caption"], magnification=magn, measure_only=True) + (row_gap//2)
            if acc>0: acc -= (row_gap//2)
            col_heights.append(acc)
        row_h = max(col_heights) if col_heights else 0

        # Center the row if it has fewer columns than the max
        row_width = cols * cell_w + (cols - 1) * gutter_x
        draw_x = margin + ( (page_w - 2*margin) - row_width ) // 2

        for col_idx, grp in enumerate(row_groups):
            y_cursor = start_y + (row_h - col_heights[col_idx])//2
            for item in grp:
                path = f_map.get(f"f{item['id']:02d}", "")
                magn = MAGNIFY_FACTOR if item.get("is_main") else 1.0
                used = draw_cell(draw_x, y_cursor, path, item["caption"], magnification=magn, measure_only=False)
                y_cursor += used + (row_gap//2)
            draw_x += cell_w + gutter_x
        return row_h

    for row_groups in rows_groups:
        if not row_groups: continue
        used_h = draw_group_row(row_groups, y, max_cols=max_cols_in_founder_rows)
        y += used_h + row_gap

    # Parakāla grid
    y += section_gap_extra
    y = draw_separator_block(canvas, y, SECTION2_TITLE, SECTION2_SUB, main_size=section2_title_size, sub_size=section2_sub_size)
    y += section_gap_extra

    total_gutter = (num_cols-1)*gutter_x
    cell_w = (page_w - 2*margin - total_gutter)//num_cols
    x0 = margin

    def draw_cell_grid(x:int, y0:int, img_path:str, caption:str) -> int:
        img_w_max = cell_w
        img_h_tgt = int(img_w_max*img_scale)
        im_src = open_rgba(img_path)
        iw, ih = im_src.size
        s = min(img_w_max/iw, img_h_tgt/ih)
        w, h = max(1,int(iw*s)), max(1,int(ih*s))
        im_circ, comb_mask, circle_mask = make_circular(im_src, w, h)

        ix = x + (cell_w-w)//2
        maybe_draw_shadow(canvas, circle_mask, (ix, y0))
        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=2)
        canvas.alpha_composite(stroke,(ix-2,y0-2))
        canvas.alpha_composite(im_circ,(ix,y0))

        cap_font = load_font(caption_font)
        max_text_w = int(cell_w * 0.9)
        lines = wrap_text_to_width(caption, cap_font, max_text_w)
        ty = y0 + h + 6
        if lines:
            max_lw = max(_text_size(ImageDraw.Draw(canvas), li, cap_font)[0] for li in lines)
            total_h = sum(_text_size(ImageDraw.Draw(canvas), li, cap_font)[1] for li in lines) + (len(lines)-1)*4
            bg = canvas.crop((x+(cell_w-max_lw)//2, ty, x+(cell_w-max_lw)//2+max_lw, ty+total_h))
            fg, sh_color_base = get_adaptive_colors(bg)
        else:
            fg, sh_color_base = (70,50,0),(30,20,0)
        s_off = get_shadow_offset(2)
        for li in lines:
            lw,lh=_text_size(ImageDraw.Draw(canvas), li, cap_font); tx=x+(cell_w-lw)//2
            ImageDraw.Draw(canvas).text((tx+s_off[0],ty+s_off[1]), li, font=cap_font, fill=sh_color_base)
            ImageDraw.Draw(canvas).text((tx,          ty          ), li, font=cap_font, fill=fg)
            ty += lh + 4
        print_font_choice_once()
        return ty - y0

    # draw Parakāla rows
    idx=0
    while idx < len(parakala_data):
        row_items = []
        for it in parakala_data[idx: idx+num_cols]:
            code = f"{it['id']:02d}00"
            row_items.append((p_map.get(code, ""), it['caption']))

        # Center the row if it has fewer items than num_cols
        row_width = len(row_items) * cell_w + (len(row_items) - 1) * gutter_x
        start_x = margin + ( (page_w - 2*margin) - row_width ) // 2

        row_h = 0
        for col, (p,cap) in enumerate(row_items):
            x = start_x + col*(cell_w+gutter_x)
            used = draw_cell_grid(x, y, p, cap)
            row_h = max(row_h, used)
        y += row_h + row_gap
        idx += num_cols

    return canvas, y

# ---------- Footer & Signature (anchored to bottom) ----------
def draw_footer_and_signature(canvas: Image.Image, page_w: int, page_h: int, margin: int, footer_font_size: int):
    d = ImageDraw.Draw(canvas)
    footer_font = load_font(footer_font_size, weight=FOOTER_FONT_WEIGHT)
    lw, footer_h = _text_size(d, FOOTER_TEXT, footer_font)

    footer_y = page_h - margin - footer_h  # bottom anchored
    strip_pad = 12
    bg_strip = canvas.crop((margin, max(0, footer_y - strip_pad), page_w - margin, min(page_h, footer_y + footer_h + strip_pad)))
    fg, sh = get_adaptive_colors(bg_strip)
    s_off = get_shadow_offset(3)

    # centered footer text
    tx = (page_w - lw)//2
    d.text((tx+s_off[0], footer_y+s_off[1]), FOOTER_TEXT, font=footer_font, fill=sh)
    d.text((tx,          footer_y          ), FOOTER_TEXT, font=footer_font, fill=fg)

    # signature to the right of footer text on the same baseline
    if SHOW_SIGNATURE and os.path.isfile(SIGNATURE_PATH):
        try:
            # Load and scale signature to fit footer height
            sig = Image.open(SIGNATURE_PATH).convert("RGBA")
            max_sig_h = footer_h * 1.2 # Allow it to be slightly taller than text
            if sig.height > max_sig_h:
                r = max_sig_h / sig.height
                sig = sig.resize((max(1,int(sig.width*r)), int(max_sig_h)), Image.LANCZOS)

            # Calculate position based on SIGNATURE_POSITION
            drawable_width = page_w - 2*margin - sig.width
            pos_frac = max(0.0, min(1.0, SIGNATURE_POSITION))
            sig_x = margin + int(drawable_width * pos_frac)
            
            # Align baseline of signature with baseline of footer text
            sig_y = footer_y + footer_h - sig.height
            canvas.alpha_composite(sig, (sig_x, sig_y))
        except Exception as e:
            print(f">>> WARNING: signature render failed: {e}")

# ---------- Auto-fit with binary search ----------
def render_with_auto_fit(page_w=4961, page_h=7016, margin=90, num_cols=6, gutter_x=30, row_gap=34,
                         title_font=180, subtitle_font=66, caption_font=42, footer_font=52,
                         img_scale=0.68, section_gap_extra=90, section2_title_size=120, section2_sub_size=62,
                         banner_max_height_fraction=0.05, parchment_brightness=1.0, parchment_mode='stretch',
                         featured_acharya_mode=True, xlsx_path: Optional[str] = None) -> Optional[Image.Image]:
    founders_data, parakala_data = read_xlsx(xlsx_path)
    f_map, p_map = index_images(IMAGES_DIR)

    # Measure footer band
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    fnt = load_font(footer_font, weight=FOOTER_FONT_WEIGHT)
    footer_h = dummy.textbbox((0,0), FOOTER_TEXT, font=fnt)[3]
    safety_gap = 16
    footer_top = page_h - margin - footer_h
    content_limit = footer_top - safety_gap  # content must end above this

    # Binary search for a scale that fits content under content_limit
    lo, hi = 0.50, 0.90  # allowed bounds for img_scale
    best_scale = None

    # Start with requested img_scale if inside bounds
    start_scale = min(max(img_scale, lo), hi)

    def measure(scale: float) -> Tuple[Image.Image, int]:
        return render_content(page_w,page_h,margin,num_cols,gutter_x,row_gap,
                              title_font,subtitle_font,caption_font,
                              scale,section_gap_extra,section2_title_size,section2_sub_size,
                              banner_max_height_fraction,parchment_brightness,parchment_mode,featured_acharya_mode,
                              founders_data=founders_data, parakala_data=parakala_data,
                              founders_map=f_map, parakala_map=p_map, xlsx_path=xlsx_path)

    # First measure
    canvas, end_y = measure(start_scale)
    if end_y <= content_limit:
        best_scale = start_scale
    else:
        # Narrow down with bsearch
        for _ in range(16):
            mid = (lo + hi) / 2.0
            canvas, end_y = measure(mid)
            if end_y <= content_limit:
                best_scale = mid
                lo = mid  # we can try bigger
            else:
                hi = mid  # too big, go smaller
        if best_scale is None:
            # fallback to the smallest we tried
            best_scale = hi
            canvas, end_y = measure(best_scale)

    # If we measured with a scale different from start_scale, re-render at best_scale to be sure
    if abs(best_scale - start_scale) > 1e-6:
        canvas, end_y = measure(best_scale)

    # As a final clamp, if still a pixel or two over, draw a thin separator
    if end_y > content_limit:
        sep = Image.new("RGBA", (page_w - 2*margin, 2), (0,0,0,60))
        canvas.alpha_composite(sep, (margin, max(margin, content_limit - 6)))

    # Footer & signature (bottom anchored)
    draw_footer_and_signature(canvas, page_w, page_h, margin, footer_font_size=footer_font)
    return canvas.convert("RGB")

# ---------- Main ----------
def main():
    # --- User Input ---
    language_input = input("Enter language (English/Kannada/Telugu/Tamil/Sanskrit) [default: English]: ").strip()
    language_choice = resolve_language_choice(language_input)
    try:
        xlsx_path = resolve_xlsx_path(language_choice)
    except FileNotFoundError as e:
        print(f">>> WARNING: {e}")
        language_choice = "english"
        try:
            xlsx_path = resolve_xlsx_path(language_choice)
        except FileNotFoundError as e2:
            print(f">>> ERROR: English spreadsheet not found either: {e2}")
            return
    banner_messages = load_banner_messages(xlsx_path, DEFAULT_BANNER_MESSAGES)
    apply_banner_messages(banner_messages)
    global XLSX_PATH, SELECTED_LANGUAGE
    XLSX_PATH = xlsx_path
    SELECTED_LANGUAGE = language_choice

    size_choice = input("Enter poster size (A1 or A2) [default: A2]: ").strip().upper() or "A2"
    if size_choice not in ["A1", "A2"]:
        print(f"Invalid size '{size_choice}'. Defaulting to A2.")
        size_choice = "A2"

    format_choice = input("Enter output format (PDF or PNG) [default: PDF]: ").strip().upper() or "PDF"
    if format_choice not in ["PDF", "PNG"]:
        print(f"Invalid format '{format_choice}'. Defaulting to PDF.")
        format_choice = "PDF"

    print(f"\n>>> Generating {size_choice} poster as a {format_choice} file...")
    print(f">>> Language: {language_choice.title()} | Spreadsheet: {os.path.basename(xlsx_path)}")

    # --- Size and Layout Configuration ---
    if size_choice == "A1":
        # A1 @ 300 DPI: 7016 x 9921 px
        page_w, page_h = 7016, 9921
        margin, num_cols, gutter_x, row_gap = 120, 7, 40, 45
        title_font, subtitle_font, caption_font, footer_font = 240, 88, 56, 70
        section2_title_size, section2_sub_size = 160, 82
    else: # A2 (default)
        # A2 @ 300 DPI: 4961 x 7016 px
        page_w, page_h = 4961, 7016
        margin, num_cols, gutter_x, row_gap = 90, 6, 30, 34
        title_font, subtitle_font, caption_font, footer_font = 180, 66, 42, 52
        section2_title_size, section2_sub_size = 120, 62

    final = render_with_auto_fit(
        page_w=page_w, page_h=page_h,
        margin=margin, num_cols=num_cols, gutter_x=gutter_x, row_gap=row_gap,
        title_font=title_font, subtitle_font=subtitle_font, caption_font=caption_font, footer_font=footer_font,
        img_scale=0.68, section_gap_extra=90,
        section2_title_size=section2_title_size, section2_sub_size=section2_sub_size,
        banner_max_height_fraction=0.05,
        parchment_brightness=PARCHMENT_BRIGHTNESS, parchment_mode=PARCHMENT_MODE,
        featured_acharya_mode=FEATURED_ACHARYA_MODE,
        xlsx_path=xlsx_path
    )

    if final is None:
        print("Render failed."); return

    # --- Save Output ---
    base_name = f"Sri_Parakala_Matham_Guru_Parampara_GRID_{size_choice}"
    if format_choice == "PDF":
        output_path = os.path.join(HERE, f"{base_name}.pdf")
        final.save(output_path, "PDF", resolution=300.0, quality=95)
    else: # PNG
        output_path = os.path.join(HERE, f"{base_name}.png")
        final.save(output_path, quality=95)

    print("\nSuccess! Saved poster to:")
    print(output_path)

if __name__ == "__main__":
    main()
