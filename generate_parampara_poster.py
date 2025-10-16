# build_poster_from_xlsx.py
# A2 poster: Founders (F00 featured; F01..F17 in exactly 2 rows with contemporaries)
# + Parakāla Jeeyars (IDs 1..36 mapped to image prefixes 0100..3600).
# Fixes in this version:
#   - SHADOW_MODE switch: "none" (default) or "directional" for realistic shadows
#   - Shadows (when enabled) are strictly circular and directional (no straight edges)
#   - NumPy premultiply-based resize to avoid Pillow ImageMath deprecation warnings
# Deps: pip install pillow pandas openpyxl numpy

import os, re, sys, glob, math
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

print(">>> Python:", sys.executable)

# ---------- Text ----------
TITLE_TEXT      = "Sri Parakala Matham Guru Parampara"
SUBTITLE_TEXT   = "Established by Sri Vedanta Desika in 1359 CE"
FOOTER_TEXT     = "Sri Parakala Matham – The Eternal Lineage of Sri Vedanta Desika"
SECTION2_TITLE  = "Sri Parakāla Jeeyars"
SECTION2_SUB    = "Lineage of Brahmatantra Svatantra Swamis"

# ---------- Style / Flags ----------
TITLE_FONT_WEIGHT    = "Bold"
SUBTITLE_FONT_WEIGHT = "Bold"
SECTION_FONT_WEIGHT  = "Bold"
FOOTER_FONT_WEIGHT   = "Bold"

# ---------- Shadow switches ----------
SHADOW_MODE = "none"        # "none" | "directional"
# when SHADOW_MODE="directional", the controls below apply
SHADOW_COLOR_HEX: Optional[str] = None  # None = adaptive
SHADOW_OPACITY   = 180
SHADOW_DIRECTION = "SW"  # NW, NE, SW, SE, CE

IMAGE_SHADOW_STRENGTH = 6   # pixel offset for image shadows (when enabled)
IMAGE_SHADOW_BLUR     = 8   # Gaussian radius
MAGNIFY_FACTOR        = 1.10  # +10% for 'M' founders

FOUNDERS_ROWS         = 2
OVERLAY_CORNERS       = []    # no corner overlays by default
PARCHMENT_MODE        = "stretch"
PARCHMENT_BRIGHTNESS  = 0.85
FEATURED_ACHARYA_MODE = True  # F00 on top
SHOW_SIGNATURE        = False

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
OUT_A2 = os.path.join(HERE, "Sri_Parakala_Matham_Guru_Parampara_GRID_A2.png")

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
    dark_text = (101,67,33); light_text = (255,245,220)
    dark_shadow=(30,20,0);   light_shadow=(40,25,10)
    return (dark_text,dark_shadow) if luma>128 else (light_text,dark_shadow)

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

def draw_banner(canvas, y, page_w, margin, max_height_fraction=0.05, feather_radius=42, gold_tint_alpha=44, desaturate=0.90):
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

    # soft shadow from alpha (only if enabled)
    if SHADOW_MODE == "directional" and IMAGE_SHADOW_STRENGTH>0 and IMAGE_SHADOW_BLUR>0:
        mask = b.getchannel('A')
        sh_col = (40,25,10,150) if not SHADOW_COLOR_HEX else (*_hex_to_rgb(SHADOW_COLOR_HEX), SHADOW_OPACITY)
        sh = Image.new("RGBA", b.size, sh_col)
        sh.putalpha(mask)
        sh = sh.filter(ImageFilter.GaussianBlur(radius=IMAGE_SHADOW_BLUR))
        off = get_shadow_offset(IMAGE_SHADOW_STRENGTH)
        sx = (canvas.width-new_w)//2 + off[0]; sy = y + off[1]
        canvas.alpha_composite(sh,(sx,sy))

    x = (canvas.width-new_w)//2
    canvas.alpha_composite(b, (x,y))
    return y + new_h + 20

# ---------- Alpha-safe image helpers ----------
def open_rgba(path: str) -> Image.Image:
    """Open image as RGBA; for missing, return gray placeholder RGBA."""
    try:
        im = Image.open(path).convert("RGBA")
        return im
    except Exception:
        im = Image.new("RGBA", (400, 400), (230,230,230,255))
        d  = ImageDraw.Draw(im)
        d.rectangle([0,0,399,399], outline=(120,120,120,255), width=2)
        d.text((10,10), "Missing image", fill=(80,80,80,255))
        return im

def resize_rgba_premultiplied(im: Image.Image, new_w: int, new_h: int) -> Image.Image:
    """Resize RGBA without fringe by premultiplying alpha before scaling (NumPy; no ImageMath.eval)."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    im_np = np.array(im, dtype=np.uint8)         # H x W x 4
    rgb = im_np[..., :3].astype(np.float32)
    a   = im_np[..., 3:4].astype(np.float32)     # keep 4th dim

    # Premultiply
    rgb_p = (rgb * (a / 255.0))

    # Stack premultiplied + alpha back
    premul = np.concatenate([rgb_p, a], axis=-1).astype(np.float32)
    premul_img = Image.fromarray(np.clip(premul, 0, 255).astype(np.uint8), "RGBA")

    # Resize premultiplied
    premul_resized = premul_img.resize((new_w, new_h), Image.LANCZOS)

    # Unpremultiply (avoid div0)
    pm_np = np.array(premul_resized, dtype=np.uint8).astype(np.float32)
    rgb_p2 = pm_np[..., :3]
    a2     = pm_np[..., 3:4]
    denom  = np.maximum(a2, 1.0)
    rgb_u  = 255.0 * (rgb_p2 / denom)

    out = np.concatenate([np.clip(rgb_u, 0, 255), a2], axis=-1).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def make_circular(im: Image.Image, out_w: int, out_h: int) -> Tuple[Image.Image, Image.Image, Image.Image]:
    """
    Resize RGBA to fit within (out_w, out_h) keeping aspect, then
    - combined_mask = original alpha ∧ circle  (used for the subject)
    - circle_mask   = pure circle (used for shadow to avoid any rectangular remnants)
    Returns (oval_rgba, combined_mask, circle_mask)
    """
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    iw, ih = im.size
    scale = min(out_w/iw, out_h/ih)
    w = max(1, int(iw*scale)); h = max(1, int(ih*scale))

    # alpha-safe resize
    im = resize_rgba_premultiplied(im, w, h)

    # original alpha after resize
    _, _, _, a = im.split()
    # circular mask
    circle_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(circle_mask).ellipse([0,0,w-1,h-1], fill=255)
    # combined mask (AND) → avoids rectangular edges and respects PNG transparency
    combined_mask = ImageChops.multiply(a, circle_mask)

    # put mask back
    im.putalpha(combined_mask)
    return im, combined_mask, circle_mask

def shadow_from_mask(mask: Image.Image, color=(40,25,10,150), blur=8) -> Image.Image:
    """Create blurred shadow from given alpha mask."""
    sh = Image.new("RGBA", mask.size, color)
    sh.putalpha(mask)
    if blur > 0:
        sh = sh.filter(ImageFilter.GaussianBlur(radius=blur))
    return sh

def maybe_draw_shadow(canvas: Image.Image, mask_for_shadow: Image.Image, dest_xy: Tuple[int,int]):
    """Draws a clean circular, directional shadow if enabled."""
    if SHADOW_MODE != "directional":
        return
    sh_col = (40,25,10,150) if not SHADOW_COLOR_HEX else (*_hex_to_rgb(SHADOW_COLOR_HEX), SHADOW_OPACITY)
    sh = shadow_from_mask(mask_for_shadow, color=sh_col, blur=IMAGE_SHADOW_BLUR)
    off = get_shadow_offset(IMAGE_SHADOW_STRENGTH)
    canvas.alpha_composite(sh, (dest_xy[0] + off[0], dest_xy[1] + off[1]))

# ---------- Data ----------
def read_xlsx():
    if not os.path.isfile(XLSX_PATH):
        raise FileNotFoundError(f"Data file not found: {XLSX_PATH}")
    df_f = pd.read_excel(XLSX_PATH, sheet_name="Founders_Early_Acharyas", engine="openpyxl", header=None)
    df_p = pd.read_excel(XLSX_PATH, sheet_name="acharyan_captions",   engine="openpyxl", header=None)

    # Founders: optional header skip
    try: first_val_f = str(df_f.iloc[0,1]).lower()
    except: first_val_f = ""
    if any(k in first_val_f for k in ("acharya","name","caption","ācārya","āchārya")):
        df_f = df_f.iloc[1:].reset_index(drop=True)

    founders = []
    for i,row in df_f.iterrows():
        if len(row)<2: continue
        try:
            fid  = int(row.iloc[0])             # col1: ID (0..17)
            cap  = str(row.iloc[1]).strip()     # col2: caption
            grp  = row.iloc[2] if len(row)>2 else None  # col3: group id
            grp  = int(grp) if pd.notna(grp) else f"unique_{i}"
            is_m = False
            if len(row)>3:
                is_m = str(row.iloc[3]).strip().upper()=='M'
            founders.append({"id": fid, "caption": cap, "group_id": grp, "is_main": is_m})
        except Exception:
            continue

    # Parakāla: optional header skip
    try: first_val_p = str(df_p.iloc[0,0]).lower()
    except: first_val_p = ""
    if any(k in first_val_p for k in ("sl no","id","no","s.no")):
        df_p = df_p.iloc[1:].reset_index(drop=True)

    parakala = []
    for _,row in df_p.iterrows():
        if len(row)<2: continue
        try:
            pid = int(row.iloc[0])              # 1..36 (Excel)
            cap = str(row.iloc[1]).strip()
            if cap:
                parakala.append({"id": pid, "caption": cap})
        except Exception:
            continue
    return founders, parakala

# ---------- Image indexing ----------
def index_images(images_dir: str):
    """
    founders_map: 'f00'..'f17' -> path
    parakala_map: '0100'..'3600' -> path  (match code anywhere in filename)
    """
    founders_map: Dict[str,str] = {}
    parakala_map: Dict[str,str] = {}

    re_f_any = re.compile(r'[fF](\d{2})') if RELAXED_MATCH_ANYWHERE else re.compile(r'^[fF](\d{2})')
    re_p_any = re.compile(r'(\d{4})')     if RELAXED_MATCH_ANYWHERE else re.compile(r'^(\d{4})')

    files = os.listdir(images_dir)
    if not files:
        print(f">>> WARNING: images folder is empty: {images_dir}")

    for fn in files:
        fn_low = fn.lower()
        if not fn_low.endswith(IMG_EXTS):
            continue
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

# ---------- Render core ----------
def render_once_A2(page_w:int, page_h:int, margin:int, num_cols:int, gutter_x:int, row_gap:int,
                   title_font:int, subtitle_font:int, caption_font:int, footer_font:int,
                   img_scale:float, section_gap_extra:int, section2_title_size:int, section2_sub_size:int,
                   banner_max_height_fraction:float, parchment_brightness:float=1.0,
                   parchment_mode:str='stretch', featured_acharya_mode:bool=True) -> Tuple[Image.Image, int]:

    founders_data, parakala_data = read_xlsx()
    f_map, p_map = index_images(IMAGES_DIR)

    # Map founders
    featured = None
    grouped: Dict[str, List[dict]] = {}
    for it in founders_data:
        fid = it['id']
        key = f"f{fid:02d}"
        path = f_map.get(key, "")
        if fid == 0 and featured_acharya_mode:
            featured = {**it, "path": path}
        else:
            gid = str(it['group_id'])
            grouped.setdefault(gid, []).append({**it, "path": path})

    # Map Parakāla — Excel 1..36 -> filenames 0100..3600
    parakala_pairs: List[Tuple[str,str]] = []
    missing = []
    for it in parakala_data:
        code = f"{it['id']:02d}00"  # 1 -> 0100, ..., 36 -> 3600
        path = p_map.get(code, "")
        if not path:
            missing.append(code)
        parakala_pairs.append((path, it['caption']))
    if missing:
        print(f">>> WARNING: {len(missing)} Parakāla codes not found (expect 0100..3600). First few: {missing[:10]}")

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
    y = draw_banner(canvas, y, page_w, margin, max_height_fraction=banner_max_height_fraction,
                    feather_radius=44, gold_tint_alpha=48, desaturate=0.88)
    y = draw_centered_text(canvas, TITLE_TEXT, y, title_font, color=None, shadow_strength=5,
                           font_weight=TITLE_FONT_WEIGHT, max_width=int(page_w*0.92), line_gap=12)
    y = draw_centered_text(canvas, SUBTITLE_TEXT, y+8, subtitle_font, color=None, shadow_strength=3,
                           font_weight=SUBTITLE_FONT_WEIGHT, max_width=int(page_w*0.92), line_gap=10)
    y += 22

    # ---------- Featured F00 ----------
    if featured:
        img_w_max = int(page_w*0.22)
        img_h_tgt = int(img_w_max*img_scale*1.2)
        im = open_rgba(featured["path"])
        iw, ih = im.size
        s = min(img_w_max/iw, img_h_tgt/ih)
        w, h = max(1,int(iw*s)), max(1,int(ih*s))

        im_circ, comb_mask, circle_mask = make_circular(im, w, h)

        # shadow (if enabled)
        x_center = (page_w - w)//2
        maybe_draw_shadow(canvas, circle_mask, (x_center, y))

        # stroke + subject
        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=3)
        canvas.alpha_composite(stroke,(x_center-2,y-2))
        canvas.alpha_composite(im_circ,(x_center,y))

        # caption
        y2 = y + h + 12
        cap_font = load_font(42, weight=FOOTER_FONT_WEIGHT)
        lw,lh = _text_size(d, featured["caption"], cap_font)
        bg = canvas.crop(((page_w-lw)//2, y2, (page_w+lw)//2, y2+lh))
        fg,sh = get_adaptive_colors(bg)
        d.text(((page_w-lw)//2+2, y2+2), featured["caption"], font=cap_font, fill=sh)
        d.text(((page_w-lw)//2,   y2),   featured["caption"], font=cap_font, fill=fg)
        y = y2 + lh + 28

    # ---------- Founders in EXACTLY 2 rows; contemporaries stacked ----------
    grouped_plain: Dict[str, List[dict]] = {}
    for it in founders_data:
        if it['id'] == 0 and FEATURED_ACHARYA_MODE:  # already drawn
            continue
        gid = str(it['group_id'])
        grouped_plain.setdefault(gid, []).append(it)

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
                # shadow (if enabled)
                ix = x + (cell_w - w)//2
                maybe_draw_shadow(canvas, circle_mask, (ix, y0))

                # stroke + subject
                stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
                ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=2)
                canvas.alpha_composite(stroke,(ix-2,y0-2))
                canvas.alpha_composite(im_circ,(ix,y0))

            cap_font = load_font(caption_font)
            words = caption.split(); lines=[]; line=""
            max_text_w = cell_w - 6
            dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
            measurer = dummy if measure_only else ImageDraw.Draw(canvas)
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
                fg,sh = get_adaptive_colors(bg)
            else:
                fg,sh = (70,50,0),(30,20,0)
            for li in lines:
                lw,lh=_text_size(measurer, li, cap_font); tx=x+(cell_w-lw)//2
                d.text((tx+2, ty+2), li, font=cap_font, fill=sh)
                d.text((tx,   ty  ), li, font=cap_font, fill=fg)
                ty += lh + 3
            print_font_choice_once()
            return ty - y0

        # measure col heights
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

        # draw
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

    # ---------- Parakāla grid ----------
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

        # shadow (if enabled)
        ix = x + (cell_w-w)//2
        maybe_draw_shadow(canvas, circle_mask, (ix, y0))

        # stroke + subject
        stroke = Image.new("RGBA", (w+4, h+4), (0,0,0,0))
        ImageDraw.Draw(stroke).ellipse([0,0,w+3,h+3], outline=(212,175,55,255), width=2)
        canvas.alpha_composite(stroke,(ix-2,y0-2))
        canvas.alpha_composite(im_circ,(ix,y0))

        cap_font = load_font(caption_font)
        words = caption.split(); lines=[]; line=""
        max_text_w = cell_w - 6
        for tk in words:
            test=(line+" "+tk).strip(); tw,_=_text_size(d,test,cap_font)
            if tw<=max_text_w or not line: line=test
            else: lines.append(line); line=tk
        if line: lines.append(line)
        ty = y0 + h + 6
        if lines:
            max_lw = max(_text_size(d, li, cap_font)[0] for li in lines)
            total_h = sum(_text_size(d, li, cap_font)[1] for li in lines) + (len(lines)-1)*3
            bg = canvas.crop((x+(cell_w-max_lw)//2, ty, x+(cell_w-max_lw)//2+max_lw, ty+total_h))
            fg,sh = get_adaptive_colors(bg)
        else:
            fg,sh=(70,50,0),(30,20,0)
        for li in lines:
            lw,lh=_text_size(d, li, cap_font); tx=x+(cell_w-lw)//2
            ImageDraw.Draw(canvas).text((tx+2,ty+2), li, font=cap_font, fill=sh)
            ImageDraw.Draw(canvas).text((tx,  ty  ), li, font=cap_font, fill=fg)
            ty += lh + 3
        print_font_choice_once()
        return ty - y0

    idx=0
    while idx < len(parakala_pairs):
        row_items = parakala_pairs[idx: idx+num_cols]
        row_h = 0
        for col, (p,cap) in enumerate(row_items):
            x = x0 + col*(cell_w+gutter_x)
            used = draw_cell_grid(x, y, p, cap)
            if used>row_h: row_h = used
        y += row_h + row_gap
        idx += num_cols

    footer_y = y + 24
    draw_centered_text(canvas, FOOTER_TEXT, footer_y, footer_font, color=None, shadow_strength=4,
                       font_weight=FOOTER_FONT_WEIGHT, max_width=int(page_w*0.92))
    return canvas.convert("RGB"), footer_y

# Separator block (placed after because it depends on draw_centered_text)
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

# ---------- Auto-fit wrapper ----------
def render_with_auto_fit(page_w=4961, page_h=7016, margin=90, num_cols=6, gutter_x=30, row_gap=34,
                         title_font=180, subtitle_font=66, caption_font=42, footer_font=48,
                         img_scale=0.68, section_gap_extra=90, section2_title_size=120, section2_sub_size=62,
                         banner_max_height_fraction=0.05, parchment_brightness=1.0, parchment_mode='stretch',
                         featured_acharya_mode=True) -> Optional[Image.Image]:
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    fnt = load_font(footer_font, weight=FOOTER_FONT_WEIGHT)
    footer_h = dummy.textbbox((0,0), FOOTER_TEXT, font=fnt)[3]
    required_bottom_space = footer_h + 40

    ideal_scale = 0.72
    _, end_y = render_once_A2(page_w,page_h,margin,num_cols,gutter_x,row_gap,title_font,subtitle_font,
                              caption_font,footer_font,ideal_scale,section_gap_extra,section2_title_size,section2_sub_size,
                              banner_max_height_fraction,parchment_brightness,parchment_mode,featured_acharya_mode)
    target_y = page_h - required_bottom_space
    if end_y > target_y:
        ratio = target_y / end_y
        final_scale = max(0.60, round(ideal_scale * ratio, 3))
        print(f">>> Overflow {end_y-target_y}px. Scale → {final_scale}")
    else:
        final_scale = ideal_scale

    img, end_y2 = render_once_A2(page_w,page_h,margin,num_cols,gutter_x,row_gap,title_font,subtitle_font,
                                 caption_font,footer_font,final_scale,section_gap_extra,section2_title_size,section2_sub_size,
                                 banner_max_height_fraction,parchment_brightness,parchment_mode,featured_acharya_mode)
    if end_y2 > target_y:
        bump = max(0.60, round(final_scale - 0.02, 3))
        print(f">>> Minor overflow; retry at {bump}")
        img, _ = render_once_A2(page_w,page_h,margin,num_cols,gutter_x,row_gap,title_font,subtitle_font,
                                caption_font,footer_font,bump,section_gap_extra,section2_title_size,section2_sub_size,
                                banner_max_height_fraction,parchment_brightness,parchment_mode,featured_acharya_mode)
    return img

# ---------- Main ----------
def main():
    final = render_with_auto_fit(
        page_w=4961, page_h=7016,     # A2 @ ~300dpi
        margin=90, num_cols=6, gutter_x=30, row_gap=34,
        title_font=180, subtitle_font=66, caption_font=42, footer_font=48,
        img_scale=0.68, section_gap_extra=90,
        section2_title_size=120, section2_sub_size=62,
        banner_max_height_fraction=0.05,
        parchment_brightness=PARCHMENT_BRIGHTNESS, parchment_mode=PARCHMENT_MODE,
        featured_acharya_mode=FEATURED_ACHARYA_MODE
    )
    if final is None:
        print("Render failed."); return
    final.save(OUT_A2, quality=95)
    print("Saved:", OUT_A2)
    pdf_path = OUT_A2.replace(".png",".pdf")
    final.save(pdf_path, "PDF", resolution=300.0, quality=95)
    print("Saved:", pdf_path)

if __name__ == "__main__":
    main()
