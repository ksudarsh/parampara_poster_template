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

import os, re, sys, glob, math, unicodedata, shutil, html
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

# ---------- Text ----------
TITLE_TEXT      = "Sri Parakala Matham Guru Parampara"
SUBTITLE_TEXT   = "Established by Sri Vedanta Desika in 1359 CE"
FOOTER_TEXT     = "Sri Parakala Swamy Mutt – The Eternal Lineage of Sri Vedanta Desika"
SECTION2_TITLE  = "Sri Parakāla Acharyas"
SECTION2_SUB    = "Lineage of Brahmatantra Svatantra Swamis"

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

MAGNIFY_FACTOR        = 1.25  # +10% for 'M' founders
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
XLSX_PATH   = os.path.join(HERE, "acharyan_captions.xlsx")

PARCHMENT_PATH    = os.path.join(ASSETS_DIR, "parchment_bg.jpg")
MANDALA_TILE_PATH = os.path.join(ASSETS_DIR, "mandala_tile.png")
SIGNATURE_PATH    = os.path.join(ASSETS_DIR, "signature.png")
OUT_A2            = os.path.join(HERE, "Sri_Parakala_Matham_Guru_Parampara_GRID_A2.png")
HTML_EXPORT_DIR   = os.path.join(HERE, "html_parampara_chart")
HTML_IMAGES_DIR   = os.path.join(HTML_EXPORT_DIR, "images")
HTML_FOUNDERS_PATH = os.path.join(HTML_EXPORT_DIR, "founders_and_early_acharyas.html")
HTML_PARAKALA_PATH = os.path.join(HTML_EXPORT_DIR, "sri_parakala_acharyas.html")
HTML_IMAGE_BASE_URL = "images/"

# ---------- Fonts ----------
_FONT_USED = None
_PRINTED_FONT = False
_FONT_CACHE: Dict[Tuple[int,str], ImageFont.FreeTypeFont] = {}

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

def load_font(size: int, weight: str = 'normal') -> ImageFont.FreeTypeFont:
    key = (size, weight.lower())
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    weight_map = {
        'normal': ["GentiumPlus-Regular.ttf","GentiumBookPlus-Regular.ttf","NotoSerif-Regular.ttf","DejaVuSerif.ttf"],
        'bold'  : ["GentiumPlus-Bold.ttf","GentiumBookPlus-Bold.ttf","NotoSerif-Bold.ttf","DejaVuSerif-Bold.ttf"],
    }
    pref_names = [n.lower() for n in weight_map.get(weight.lower(), weight_map['normal'])]
    found = _find_fonts_recursively(FONTS_DIR)
    preferred = [p for p in found if os.path.basename(p).lower() in pref_names]
    preferred.sort(key=lambda p: pref_names.index(os.path.basename(p).lower()) if os.path.basename(p).lower() in pref_names else 999)
    others = [p for p in found if p not in preferred]
    f = _try_load_font(size, preferred + others)
    if not f:
        candidates = [
            r"C:\Windows\Fonts\GentiumPlus-Regular.ttf", r"C:\Windows\Fonts\GentiumPlus-Bold.ttf",
            r"C:\Windows\Fonts\NotoSerif-Regular.ttf",   r"C:\Windows\Fonts\NotoSerif-Bold.ttf",
            r"C:\Windows\Fonts\Cambria.ttc", r"C:\Windows\Fonts\times.ttf", r"C:\Windows\Fonts\Nirmala.ttf",
            "/Library/Fonts/GentiumPlus-Regular.ttf", "/Library/Fonts/GentiumPlus-Bold.ttf",
            "/Library/Fonts/NotoSerif-Regular.ttf",   "/Library/Fonts/NotoSerif-Bold.ttf",
            "/usr/share/fonts/truetype/gentiumplus/GentiumPlus-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]
        f = _try_load_font(size, candidates) or ImageFont.load_default()
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

# ---------- Data ----------
def read_xlsx():
    if not os.path.isfile(XLSX_PATH):
        raise FileNotFoundError(f"Data file not found: {XLSX_PATH}")
    df_f = pd.read_excel(XLSX_PATH, sheet_name="Founders_Early_Acharyas", engine="openpyxl", header=None)
    df_p = pd.read_excel(XLSX_PATH, sheet_name="acharyan_captions",   engine="openpyxl", header=None)

    # Drop spacer columns that are entirely blank so indexes stay consistent
    df_f = df_f.dropna(axis=1, how='all')
    df_p = df_p.dropna(axis=1, how='all')

    id_col = 0
    caption_col = 1 if df_f.shape[1] > 1 else 0
    group_col = 2 if df_f.shape[1] > 2 else None
    enhance_col = 3 if df_f.shape[1] > 3 else None

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

    # Parakala: optional header skip
    try: first_val_p = normalize_ascii_lower(df_p.iloc[0,0])
    except Exception: first_val_p = ""
    if any(k in first_val_p for k in ("sl no","slno","id","no","s.no")):
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

def slugify_name(name: str) -> str:
    """Converts a name into a URL-friendly slug for anchors."""
    # Normalize accented characters to their base ASCII equivalent
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s) # remove non-alphanumeric
    s = re.sub(r'[\s-]+', '-', s).strip('-') # replace spaces/hyphens with a single hyphen
    return s

# ---------- HTML helpers ----------
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def prepare_html_image_map(founders: List[dict], parakala: List[dict],
                           founders_map: Dict[str,str], parakala_map: Dict[str,str]) -> Dict[str, Dict[str,str]]:
    ensure_dir(HTML_EXPORT_DIR)
    ensure_dir(HTML_IMAGES_DIR)
    rel_map: Dict[str, Dict[str,str]] = {}
    used_names: Dict[str,str] = {}

    def register(code: str, src: Optional[str]):
        if not src or not os.path.isfile(src):
            return
        base_name = os.path.basename(src)
        dest_name = base_name
        stem, ext = os.path.splitext(base_name)
        suffix = 1
        while dest_name.lower() in used_names and os.path.abspath(used_names[dest_name.lower()]) != os.path.abspath(src):
            dest_name = f"{stem}_{code}_{suffix}{ext}"
            suffix += 1
        dest_path = os.path.join(HTML_IMAGES_DIR, dest_name)
        if os.path.abspath(src) != os.path.abspath(dest_path):
            shutil.copy2(src, dest_path)
        used_names[dest_name.lower()] = src
        rel_map[code] = {"file": dest_name, "rel": f"images/{dest_name}"}

    for item in founders:
        code = f"f{int(item['id']):02d}".lower()
        register(code, founders_map.get(code, ""))
    for item in parakala:
        code = f"{int(item['id']):02d}00"
        register(code, parakala_map.get(code, ""))
    return rel_map

def build_founders_html_document(founders: List[dict], img_rel_map: Dict[str, Dict[str,str]]) -> str:
    """
    Builds a self-contained HTML snippet for the Founders and Early Acharyas lineage.
    """
    def card_image_html(img_meta: Optional[Dict[str,str]], alt_text: str) -> str:
        if img_meta and img_meta.get("rel"):
            local_rel_path = img_meta["rel"]
            return (f'<img src="{html.escape(local_rel_path)}" data-img-file="{html.escape(img_meta["file"])}" '
                    f'alt="{html.escape(alt_text)}" loading="lazy" decoding="async" />')
        return '<div class="img-missing">Image coming soon</div>'

    hero_block = ""
    timeline_founders = list(founders) # make a copy
    if timeline_founders and timeline_founders[0]['id'] == 0:
        hero = timeline_founders.pop(0) # F00 is hero, remove from timeline data
        hero_key = f"f{hero['id']:02d}".lower()
        hero_img_meta = img_rel_map.get(hero_key)
        hero_img_html = card_image_html(hero_img_meta, hero['caption'])
        anchor_href = f"#acharyan-{int(hero['id'])}"
        hero_block = f"""
          <a href="{anchor_href}" class="hero-link">
            <div class="hero-frame">{hero_img_html}</div>
            <figcaption class="hero-caption">{html.escape(hero['caption'])}</figcaption>
          </a>
        """

    lineage_groups = []
    seen_gids = set()
    grouped_by_gid = {}
    for i, founder in enumerate(timeline_founders):
        gid = founder['group_id']
        if gid not in grouped_by_gid: grouped_by_gid[gid] = []
        grouped_by_gid[gid].append(founder)
    # Iterate through founders to maintain original order
    for founder in timeline_founders:
        gid = founder['group_id']
        if gid in seen_gids:
            continue
        group = grouped_by_gid[gid]
        lineage_groups.append(group)
        seen_gids.add(gid)

    lineage_flow_html = build_lineage_flow_html(lineage_groups, img_rel_map, card_image_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(TITLE_TEXT)}</title>
  <style>
    :root {{
      --bg: #f8f4ec;
      --ink: #3a2411;
      --gold: #b98d28;
      --track: #d8e6fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Gentium Plus","Noto Serif","Georgia",serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px 16px 56px;
    }}
    header {{ text-align:center; margin-bottom: 14px; }}
    header h1 {{
      font-size: clamp(2.2rem, 4vw, 3.2rem);
      margin: 0 0 .35rem;
      letter-spacing: .03em;
    }}
    header p {{ margin: 0; color: #6b4d1f; font-size: clamp(1rem, 2vw, 1.25rem); }}

    /* Hero */
    a.hero-link {{ text-decoration: none; color: inherit; }}
    a.hero-link {{ display:flex; flex-direction:column; align-items:center; margin: 18px 0 24px; }}
    .hero-frame {{
      width: min(280px, 70vw);
      aspect-ratio: 1/1;
      border-radius: 999px;
      overflow: hidden;
      border: 6px solid var(--gold);
      background: transparent;
      box-shadow: 0 18px 36px rgba(0,0,0,.12);
    }}
    .hero-frame img {{ width:100%; height:100%; object-fit:cover; display:block; }}
    .hero-caption {{
      margin-top: 12px;
      font-size: 1.2rem;
      font-weight: bold;
      text-align: center;
    }}

    /* Lineage Flow */
    .lineage-flow {{ margin-top: 24px; position: relative; }}
    .lineage-row {{
      position: relative;
      padding: 28px 0 60px;
    }}
    .lineage-row .row-track {{
      position: relative;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: clamp(18px, 3vw, 60px);
      padding: 0 8%;
    }}
    .lineage-row.dir-rtl .row-track {{
      flex-direction: row-reverse;
    }}
    .lineage-step {{
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1 1 0;
      min-width: 140px;
    }}
    .timeline-card {{
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      transition: transform 0.25s ease;
    }}
    .timeline-card .image-frame {{
      width: clamp(110px, 9vw, 140px);
      aspect-ratio: 1 / 1;
      border-radius: 999px;
      border: 5px solid var(--gold);
      overflow: hidden;
      background: #fff;
      box-shadow: 0 12px 24px rgba(0,0,0,0.16);
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}
    .timeline-card img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .timeline-card figcaption {{ text-align: center; font-size: 0.95rem; line-height: 1.3; }}
    .timeline-card:hover .image-frame {{
      transform: scale(1.05);
      box-shadow: 0 18px 30px rgba(0,0,0,0.22);
    }}
    .timeline-card:focus-visible .image-frame {{
      outline: 3px solid rgba(185,141,40,0.65);
      outline-offset: 4px;
    }}


    .img-missing {{
      display:flex; align-items:center; justify-content:center;
      width:100%; height:100%; font-size:.9rem; color:#9a7736; padding:.5rem; text-align:center;
    }}

  </style>
</head>
<body>
  <main>
    <header>
      <h1>{html.escape(TITLE_TEXT)}</h1>
      <p>{html.escape(SUBTITLE_TEXT)}</p>
    </header>

    {hero_block}

    <!-- Lineage Flow -->
    {lineage_flow_html}

  </main>
  <script>
    (function() {{
      var root = window.PARAKALA_IMG_ROOT || "{HTML_IMAGE_BASE_URL}";
      if (!root) return;
      if (root.slice(-1) !== "/") root += "/";
      document.querySelectorAll("img[data-img-file]").forEach(function(img) {{
        var file = img.getAttribute("data-img-file");
        if (file) {{
          img.src = root + file;
        }}
      }});
    }})();
  </script>
</body>
</html>
"""

def build_parakala_html_document(parakala: List[dict], img_rel_map: Dict[str, Dict[str,str]]) -> str:
    """
    Builds a self-contained HTML snippet for the Sri Parakala Acharyas grid.
    """
    def card_image_html(img_meta: Optional[Dict[str,str]], alt_text: str) -> str:
        if img_meta and img_meta.get("rel"):
            local_rel_path = img_meta["rel"]
            return (f'<img src="{html.escape(local_rel_path)}" data-img-file="{html.escape(img_meta["file"])}" '
                    f'alt="{html.escape(alt_text)}" loading="lazy" decoding="async" />')
        return '<div class="img-missing">Image coming soon</div>'

    parakala_grid_html = ""
    if parakala:
        parakala_items_html = []
        for item in parakala:
            pid = int(item["id"])
            img_key = f"{pid:02d}00"
            img_meta = img_rel_map.get(img_key)
            img_html = card_image_html(img_meta, item['caption'])
            anchor_href = f"#acharyan-{pid}"
            parakala_items_html.append(f"""
              <a href="{anchor_href}" class="grid-item-link">
                <figure class="grid-item">
                  <div class="grid-item-frame">{img_html}</div>
                  <figcaption>{html.escape(item['caption'])}</figcaption>
                </figure>
              </a>
            """)
        parakala_grid_html = f"""
          <div class="parakala-grid">
            {''.join(parakala_items_html)}
          </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(SECTION2_TITLE)}</title>
  <style>
    :root {{
      --bg: #f8f4ec;
      --ink: #3a2411;
      --gold: #b98d28;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Gentium Plus","Noto Serif","Georgia",serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px 16px 56px;
    }}
    .section-header {{ text-align:center; margin: 0 0 24px; }}
    .section-header h2 {{ font-size: clamp(1.8rem, 3vw, 2.5rem); margin:0 0 4px; }}
    .section-header p {{ margin:0; color: #6b4d1f; font-size: clamp(1rem, 2vw, 1.15rem); }}
    .parakala-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 24px 16px;
      max-width: 1100px;
      margin: 0 auto;
    }}
    a.grid-item-link {{ text-decoration: none; color: inherit; display: block; }}
    .grid-item {{ margin: 0; text-align: center; display: block; }}
    .grid-item-frame {{
      width: 100%;
      aspect-ratio: 1/1;
      border-radius: 999px;
      overflow: hidden;
      border: 4px solid var(--gold);
      margin: 0 auto 8px;
      background: transparent;
      box-shadow: 0 8px 16px rgba(0,0,0,0.1);
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}
    .grid-item-frame img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .grid-item-link:hover .grid-item-frame {{
      transform: scale(1.05);
      box-shadow: 0 14px 28px rgba(0,0,0,0.18);
    }}
    .grid-item-link:focus-visible .grid-item-frame {{
      outline: 3px solid rgba(185,141,40,0.65);
      outline-offset: 4px;
    }}
    .grid-item figcaption {{ font-size: 0.9rem; line-height: 1.2; }}
    .img-missing {{
      display:flex; align-items:center; justify-content:center;
      width:100%; height:100%; font-size:.9rem; color:#9a7736; padding:.5rem; text-align:center;
    }}
     @media (max-width: 600px) {{
      .parakala-grid {{ grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="section-header">
      <h2>{html.escape(SECTION2_TITLE)}</h2>
      <p>{html.escape(SECTION2_SUB)}</p>
    </header>
    {parakala_grid_html}
  </main>
  <script>
    (function() {{
      var root = window.PARAKALA_IMG_ROOT || "{HTML_IMAGE_BASE_URL}";
      if (!root) return;
      if (root.slice(-1) !== "/") root += "/";
      document.querySelectorAll("img[data-img-file]").forEach(function(img) {{
        var file = img.getAttribute("data-img-file");
        if (file) {{
          img.src = root + file;
        }}
      }});
    }})();
  </script>
</body>
</html>
"""

def build_lineage_flow_html(lineage_groups: List[List[dict]], img_rel_map: Dict[str, Dict[str,str]], card_image_html_fn) -> str:
    if not lineage_groups:
        return ""

    all_acharyas = {item['id']: item for group in lineage_groups for item in group}

    row_configs = [
        {"ids": [1, 2, 3],    "dir": "ltr"},
        {"ids": [6, 5, 4],    "dir": "rtl"},
        {"ids": [7, 8, 9],    "dir": "ltr"},
        {"ids": [14, 12, 10], "dir": "rtl", "tag": "fork-top"},
        {"ids": [15, 13, 11], "dir": "rtl", "tag": "fork-bottom"},
        {"ids": [16, 17, 18], "dir": "ltr"}
    ]

    rows_html: List[str] = []
    for idx, cfg in enumerate(row_configs):
        row_index = idx + 1
        row_classes = ["lineage-row", f"row-{row_index}", f"dir-{cfg['dir']}"]
        if row_index == len(row_configs):
            row_classes.append("row-last")
        tag = cfg.get("tag")
        if tag:
            row_classes.append(tag)

        steps_html: List[str] = []
        for acharya_id in cfg["ids"]:
            acharya = all_acharyas.get(acharya_id)
            if not acharya:
                continue
            key = f"f{int(acharya['id']):02d}".lower()
            anchor_href = f"#acharyan-{int(acharya['id'])}"
            img_meta = img_rel_map.get(key)
            img_html = card_image_html_fn(img_meta, acharya['caption'])
            steps_html.append(
                f"""
                <div class="lineage-step">
                  <a href="{anchor_href}" class="timeline-card">
                    <div class="image-frame">{img_html}</div>
                    <figcaption>{html.escape(acharya['caption'])}</figcaption>
                  </a>
                </div>
                """
            )

        rows_html.append(
            f"""
            <div class="{' '.join(row_classes)}">
              <div class="row-track">
                {''.join(steps_html)}
              </div>
            </div>
            """
        )

    return f"""
      <section class="lineage-flow">
        <header class="section-header" style="margin-bottom: 28px;">
          <h2>Founders &amp; Early Āchāryas</h2>
        </header>
        {''.join(rows_html)}
      </section>
    """

def generate_html_bundle(founders: List[dict], parakala: List[dict],
                         founders_map: Dict[str,str], parakala_map: Dict[str,str]):
    rel_map = prepare_html_image_map(founders, parakala, founders_map, parakala_map)
    ensure_dir(HTML_EXPORT_DIR)

    # Generate and save the Founders HTML file
    founders_html_doc = build_founders_html_document(founders, rel_map)
    with open(HTML_FOUNDERS_PATH, "w", encoding="utf-8") as fh:
        fh.write(founders_html_doc)
    print(f"Saved Founders HTML to: {HTML_FOUNDERS_PATH}")

    # Generate and save the Parakala Acharyas HTML file
    parakala_html_doc = build_parakala_html_document(parakala, rel_map)
    with open(HTML_PARAKALA_PATH, "w", encoding="utf-8") as fh:
        fh.write(parakala_html_doc)
    print(f"Saved Parakala Acharyas HTML to: {HTML_PARAKALA_PATH}")

    print(f"Copied {len(rel_map)} images into: {HTML_IMAGES_DIR}")

# ---------- Separator ----------
def draw_separator_block(canvas, y, title_main, title_sub, main_size, sub_size, line_color=(212,175,55), margin=80):
    d = ImageDraw.Draw(canvas)
    y_line=y+12
    d.line((margin,y_line, canvas.width-margin, y_line), fill=line_color, width=3)
    y0 = y_line+18
    y0 = draw_centered_text(canvas, title_main, y0, main_size, color=None,
                            shadow_strength=4, font_weight=SECTION_FONT_WEIGHT,
                            max_width=int(canvas.width*0.92), line_gap=8)
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
                   founders_map: Optional[Dict[str,str]] = None, parakala_map: Optional[Dict[str,str]] = None
                   ) -> Tuple[Image.Image, int]:
    if founders_data is None or parakala_data is None:
        founders_data, parakala_data = read_xlsx()
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
    y = draw_centered_text(canvas, SUBTITLE_TEXT, y+8, subtitle_font, color=None, shadow_strength=3,
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
        cap_font = load_font(42, weight=FOOTER_FONT_WEIGHT)
        lw,lh = _text_size(d, featured["caption"], cap_font)
        bg = canvas.crop(((page_w-lw)//2, y2, (page_w+lw)//2, y2+lh))
        fg, sh_color_base = get_adaptive_colors(bg)
        s_off = get_shadow_offset(2)
        d.text(((page_w-lw)//2+s_off[0], y2+s_off[1]), featured["caption"], font=cap_font, fill=sh_color_base)
        d.text(((page_w-lw)//2,   y2),   featured["caption"], font=cap_font, fill=fg)
        y = y2 + lh + 28

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

    def draw_group_row(row_groups: List[List[dict]], start_y: int) -> int:
        if not row_groups: return 0
        cols = len(row_groups)
        total_gutter = (cols-1)*gutter_x
        cell_w = (page_w - 2*margin - total_gutter)//max(1,cols)

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
            words = caption.split(); lines=[]; line=""
            max_text_w = cell_w - 6
            measurer = ImageDraw.Draw(Image.new("RGBA",(1,1))) if measure_only else ImageDraw.Draw(canvas)
            for tk in words:
                test=(line+" "+tk).strip(); tw,_=_text_size(measurer, test, cap_font)
                if tw<=max_text_w or not line: line=test
                else: lines.append(line); line=tk
            if line: lines.append(line)
            ty = y0 + h + 6
            if measure_only:
                total_h = sum(_text_size(measurer, li, cap_font)[1] for li in lines) + (len(lines)-1)*3
                return (ty - y0) + total_h
            if lines:
                max_lw = max(_text_size(measurer, li, cap_font)[0] for li in lines)
                total_h = sum(_text_size(measurer, li, cap_font)[1] for li in lines) + (len(lines)-1)*3
                bg = canvas.crop((x+(cell_w-max_lw)//2, ty, x+(cell_w-max_lw)//2+max_lw, ty+total_h))
                fg, sh_color_base = get_adaptive_colors(bg)
            else:
                fg, sh_color_base = (70,50,0),(30,20,0)
            s_off = get_shadow_offset(2)
            for li in lines:
                lw,lh=_text_size(measurer, li, cap_font); tx=x+(cell_w-lw)//2
                ImageDraw.Draw(canvas).text((tx+s_off[0], ty+s_off[1]), li, font=cap_font, fill=sh_color_base)
                ImageDraw.Draw(canvas).text((tx,          ty          ), li, font=cap_font, fill=fg)
                ty += lh + 3
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

        draw_x = margin
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
        used_h = draw_group_row(row_groups, y)
        y += used_h + row_gap

    # Parakāla grid (for PDF/PNG only)
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
        words = caption.split(); lines=[]; line=""
        max_text_w = cell_w - 6
        for tk in words:
            test=(line+" "+tk).strip(); tw,_=_text_size(ImageDraw.Draw(canvas),test,cap_font)
            if tw<=max_text_w or not line: line=test
            else: lines.append(line); line=tk
        if line: lines.append(line)
        ty = y0 + h + 6
        if lines:
            max_lw = max(_text_size(ImageDraw.Draw(canvas), li, cap_font)[0] for li in lines)
            total_h = sum(_text_size(ImageDraw.Draw(canvas), li, cap_font)[1] for li in lines) + (len(lines)-1)*3
            bg = canvas.crop((x+(cell_w-max_lw)//2, ty, x+(cell_w-max_lw)//2+max_lw, ty+total_h))
            fg, sh_color_base = get_adaptive_colors(bg)
        else:
            fg, sh_color_base = (70,50,0),(30,20,0)
        s_off = get_shadow_offset(2)
        for li in lines:
            lw,lh=_text_size(ImageDraw.Draw(canvas), li, cap_font); tx=x+(cell_w-lw)//2
            ImageDraw.Draw(canvas).text((tx+s_off[0],ty+s_off[1]), li, font=cap_font, fill=sh_color_base)
            ImageDraw.Draw(canvas).text((tx,          ty          ), li, font=cap_font, fill=fg)
            ty += lh + 3
        print_font_choice_once()
        return ty - y0

    # draw Parakāla rows (for PDF/PNG only)
    idx=0
    while idx < len(parakala_data):
        row_items = []
        for it in parakala_data[idx: idx+num_cols]:
            code = f"{it['id']:02d}00"
            row_items.append((p_map.get(code, ""), it['caption']))
        row_h = 0
        for col, (p,cap) in enumerate(row_items):
            x = x0 + col*(cell_w+gutter_x)
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
            sig = Image.open(SIGNATURE_PATH).convert("RGBA")
            max_sig_h = footer_h * 1.2
            if sig.height > max_sig_h:
                r = max_sig_h / sig.height
                sig = sig.resize((max(1,int(sig.width*r)), int(max_sig_h)), Image.LANCZOS)
            drawable_width = page_w - 2*margin - sig.width
            pos_frac = max(0.0, min(1.0, SIGNATURE_POSITION))
            sig_x = margin + int(drawable_width * pos_frac)
            sig_y = footer_y + footer_h - sig.height
            canvas.alpha_composite(sig, (sig_x, sig_y))
        except Exception as e:
            print(f">>> WARNING: signature render failed: {e}")

# ---------- Auto-fit with binary search ----------
def render_with_auto_fit(page_w=4961, page_h=7016, margin=90, num_cols=6, gutter_x=30, row_gap=34,
                         title_font=180, subtitle_font=66, caption_font=42, footer_font=52,
                         img_scale=0.68, section_gap_extra=90, section2_title_size=120, section2_sub_size=62,
                         banner_max_height_fraction=0.05, parchment_brightness=1.0, parchment_mode='stretch',
                         featured_acharya_mode=True) -> Optional[Image.Image]:
    founders_data, parakala_data = read_xlsx()
    f_map, p_map = index_images(IMAGES_DIR)

    # Measure footer band
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    fnt = load_font(footer_font, weight=FOOTER_FONT_WEIGHT)
    footer_h = dummy.textbbox((0,0), FOOTER_TEXT, font=fnt)[3]
    safety_gap = 16
    footer_top = page_h - margin - footer_h
    content_limit = footer_top - safety_gap  # content must end above this

    # Binary search for a scale that fits content under content_limit
    lo, hi = 0.50, 0.90
    best_scale = None
    start_scale = min(max(img_scale, lo), hi)

    def measure(scale: float) -> Tuple[Image.Image, int]:
        return render_content(page_w,page_h,margin,num_cols,gutter_x,row_gap,
                              title_font,subtitle_font,caption_font,
                              scale,section_gap_extra,section2_title_size,section2_sub_size,
                              banner_max_height_fraction,parchment_brightness,parchment_mode,featured_acharya_mode,
                              founders_data=founders_data, parakala_data=parakala_data,
                              founders_map=f_map, parakala_map=p_map)

    canvas, end_y = measure(start_scale)
    if end_y <= content_limit:
        best_scale = start_scale
    else:
        for _ in range(16):
            mid = (lo + hi) / 2.0
            canvas, end_y = measure(mid)
            if end_y <= content_limit:
                best_scale = mid
                lo = mid
            else:
                hi = mid
        if best_scale is None:
            best_scale = hi
            canvas, end_y = measure(best_scale)

    if abs(best_scale - start_scale) > 1e-6:
        canvas, end_y = measure(best_scale)

    if end_y > content_limit:
        sep = Image.new("RGBA", (page_w - 2*margin, 2), (0,0,0,60))
        canvas.alpha_composite(sep, (margin, max(margin, content_limit - 6)))

    draw_footer_and_signature(canvas, page_w, page_h, margin, footer_font_size=footer_font)
    return canvas.convert("RGB")

# ---------- Main ----------
def main():
    founders_data, parakala_data = read_xlsx()
    founders_map, parakala_map = index_images(IMAGES_DIR)
    choice = {"png": True, "pdf": True, "html": False}
    try:
        resp = input("Select output format (PDF/PNG/HTML/ALL) [PDF+PNG]: ").strip().lower()
    except EOFError:
        resp = ""
    if resp:
        tokens = [tok for tok in re.split(r"[\\s,/+]+", resp) if tok]
        if any(tok == "all" for tok in tokens):
            choice = {"png": True, "pdf": True, "html": True}
        else:
            sel = {"png": False, "pdf": False, "html": False}
            for tok in tokens:
                if tok in sel: sel[tok] = True
            if any(sel.values()): choice = sel

    final = None
    if choice["png"] or choice["pdf"]:
        final = render_with_auto_fit(
            page_w=4961, page_h=7016,     # A2 @ ~300dpi
            margin=90, num_cols=6, gutter_x=30, row_gap=34,
            title_font=180, subtitle_font=66, caption_font=42, footer_font=52,
            img_scale=0.68, section_gap_extra=90,
            section2_title_size=120, section2_sub_size=62,
            banner_max_height_fraction=0.05,
            parchment_brightness=PARCHMENT_BRIGHTNESS, parchment_mode=PARCHMENT_MODE,
            featured_acharya_mode=FEATURED_ACHARYA_MODE
        )
        if final is None:
            print("Render failed.")
        else:
            if choice["png"]:
                final.save(OUT_A2, quality=95)
                print("Saved:", OUT_A2)
            if choice["pdf"]:
                pdf_path = OUT_A2.replace(".png",".pdf")
                final.save(pdf_path, "PDF", resolution=300.0, quality=95)
                print("Saved:", pdf_path)

    if choice["html"]:
        generate_html_bundle(founders_data, parakala_data, founders_map, parakala_map)

if __name__ == "__main__":
    main()
