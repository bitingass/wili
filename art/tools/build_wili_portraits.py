"""Build Wili's DST-framed oval bigportrait and localized hero name banners.

Run from the repository root:
    python art/tools/build_wili_portraits.py

Outputs:
    art/source/ui/bigportraits/wili.png        (512x1024 POT canvas, 491x654 active)
    bigportraits/wili.tex + wili.xml           (BC3 KTEX + exact Klei oval UVs)
    art/source/ui/images/names_gold_cn_wili.png (1024x512 POT canvas, 876x434 active)
    art/source/ui/images/names_gold_wili.png
    art/source/ui/images/names_wili.png
    images/names_gold_cn_wili.{tex,xml}
    images/names_gold_wili.{tex,xml}
    images/names_wili.{tex,xml}
"""
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
import encode_ktex  # noqa: E402

SOURCE_UI = ROOT / "art/source/ui"
FULLBODY = ROOT / "art/source/illustrations/ui/wili-fullbody-v1.png"
OVAL_FRAME = SOURCE_UI / "bigportraits/oval-frame-base.png"

# Exact Klei Extended Sample Character packing sizes & UVs
PORTRAIT_CONTENT = (491, 654)
PORTRAIT_POT = (512, 1024)
NAME_CONTENT = (876, 434)
NAME_POT = (1024, 512)

CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)
LATIN_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def pick_font(candidates, size):
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise FileNotFoundError(f"No suitable font found in {candidates}")


def write_atlas_xml(xml_path: Path, tex_filename: str, element_name: str, content_size, pot_size):
    cw, ch = content_size
    pw, ph = pot_size
    u1 = 0.5 / pw
    u2 = (cw - 0.5) / pw
    v1 = 1.0 - (ch - 0.5) / ph
    v2 = 1.0 - 0.5 / ph
    xml = (
        f'<Atlas><Texture filename="{tex_filename}" />'
        f'<Elements><Element name="{element_name}" '
        f'u1="{u1:.11g}" u2="{u2:.11g}" v1="{v1:.11g}" v2="{v2:.11g}" />'
        f'</Elements></Atlas>\n'
    )
    xml_path.write_text(xml, encoding="utf-8")


def build_framed_bigportrait():
    frame = Image.open(OVAL_FRAME).convert("RGBA")
    if frame.size != PORTRAIT_CONTENT:
        raise ValueError(f"Expected {PORTRAIT_CONTENT} oval frame, got {frame.size}")

    wili_src = Image.open(FULLBODY).convert("RGBA")
    wili_tight = wili_src.crop(wili_src.getbbox())

    # Fit cleanly inside the official Gothic oval frame: boots planted on the
    # etched ground plane, head clear beneath the upper crest (matches Wanda/officials).
    target_h = 432
    scale = target_h / wili_tight.height
    nw, nh = round(wili_tight.width * scale), round(wili_tight.height * scale)
    wili_scaled = wili_tight.resize((nw, nh), Image.Resampling.LANCZOS)

    wx = round((frame.width - nw) / 2) - 4
    wy = 562 - nh  # boots stand firmly inside the pale ground area (~550-570)

    composed = frame.copy()

    # Soft ground contact shadow masked to the oval frame interior
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    sdr = ImageDraw.Draw(shadow)
    sdr.ellipse((wx + round(nw * 0.08), 542, wx + round(nw * 0.88), 574), fill=(26, 26, 26, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    sh_arr = np.asarray(shadow).copy()
    fr_a = np.asarray(frame)[:, :, 3]
    sh_arr[:, :, 3] = (sh_arr[:, :, 3].astype(np.float32) * (fr_a.astype(np.float32) / 255.0)).astype(np.uint8)
    composed.alpha_composite(Image.fromarray(sh_arr, "RGBA"))

    composed.alpha_composite(wili_scaled, (wx, wy))

    # Pack top-left into 512x1024 POT canvas (exact Klei bigportraits layout)
    pot = Image.new("RGBA", PORTRAIT_POT, (0, 0, 0, 0))
    pot.paste(composed, (0, 0))

    src_png = SOURCE_UI / "bigportraits/wili.png"
    src_png.parent.mkdir(parents=True, exist_ok=True)
    pot.save(src_png)

    tex_out = ROOT / "bigportraits/wili.tex"
    xml_out = ROOT / "bigportraits/wili.xml"
    encode_ktex.encode_tex(src_png, tex_out, "bc3")
    write_atlas_xml(xml_out, "wili.tex", "wili.tex", PORTRAIT_CONTENT, PORTRAIT_POT)
    print(f"Built {src_png} -> {tex_out} & {xml_out}")
    return composed


def make_parchment_texture(w, h, gold=True):
    rng = np.random.default_rng(7)
    base_col = np.array([242.0, 215.0, 140.0]) if gold else np.array([198.0, 196.0, 188.0])
    low = rng.normal(0.0, 1.0, (h // 16 + 2, w // 16 + 2)).astype(np.float32)
    low_im = Image.fromarray(((low * 0.25 + 0.5).clip(0, 1) * 255).astype(np.uint8)).resize(
        (w, h), Image.Resampling.BICUBIC
    )
    mottle = (np.asarray(low_im, dtype=np.float32) / 255.0 - 0.5) * 28.0
    fine = rng.normal(0.0, 5.5, (h, w)).astype(np.float32)
    speck_mask = rng.random((h, w)) < 0.0020
    speck = np.where(speck_mask, -38.0 if gold else -28.0, 0.0)
    speck_im = Image.fromarray(np.clip(-speck * 4, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    speck = -np.asarray(speck_im, dtype=np.float32) / 4.0
    yg = np.linspace(10.0, -10.0, h, dtype=np.float32)[:, None]
    delta = mottle + fine + speck + yg
    scale = np.array([1.0, 0.92, 0.72]) if gold else np.array([1.0, 1.0, 1.0])
    rgb = np.clip(base_col[None, None, :] + delta[:, :, None] * scale, 0, 255)
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def render_name_banner(chars, tilts, y_shifts, font_candidates, font_size, spacing, gold=True):
    w, h = NAME_CONTENT
    mask = Image.new("L", (w, h), 0)
    font = pick_font(font_candidates, font_size)
    glyphs = []
    for ch, tilt in zip(chars, tilts):
        tmp = Image.new("L", (font_size * 2, font_size * 2), 0)
        d = ImageDraw.Draw(tmp)
        bbox = d.textbbox((0, 0), ch, font=font)
        gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((font_size - gw // 2 - bbox[0], font_size - gh // 2 - bbox[1]), ch, font=font, fill=255)
        rot = tmp.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True)
        glyphs.append(rot.crop(rot.getbbox()))

    total_w = sum(g.width for g in glyphs) + spacing * (len(glyphs) - 1)
    cur_x = (w - total_w) // 2
    for g, ys in zip(glyphs, y_shifts):
        gy = (h - g.height) // 2 + ys
        mask.paste(g, (cur_x, gy), g)
        cur_x += g.width + spacing

    # Official Klei cut-paper look: parchment fill + crisp dark drop shadow (no heavy border)
    banner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (12, 8, 4, 0))
    sh_alpha = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda a: int(a * 0.88))
    sh.putalpha(sh_alpha)
    banner.alpha_composite(sh, (11, 13))

    # Crisp subtle contact shadow directly behind glyph so gold reads on light parchment too
    sh2 = Image.new("RGBA", (w, h), (22, 16, 10, 0))
    sh2.putalpha(mask.filter(ImageFilter.GaussianBlur(2.5)).point(lambda a: int(a * 0.72)))
    banner.alpha_composite(sh2, (4, 5))

    tex = make_parchment_texture(w, h, gold=gold).convert("RGBA")
    tex.putalpha(mask)
    banner.alpha_composite(tex)
    return banner


def save_name_banner(stem: str, banner: Image.Image):
    pot = Image.new("RGBA", NAME_POT, (0, 0, 0, 0))
    pot.paste(banner, (0, 0))

    src_png = SOURCE_UI / f"images/{stem}.png"
    src_png.parent.mkdir(parents=True, exist_ok=True)
    pot.save(src_png)

    tex_out = ROOT / f"images/{stem}.tex"
    xml_out = ROOT / f"images/{stem}.xml"
    encode_ktex.encode_tex(src_png, tex_out, "bc3")
    # DST expects Element name to be "<character>.tex" inside images/names*_wili.xml
    write_atlas_xml(xml_out, f"{stem}.tex", "wili.tex", NAME_CONTENT, NAME_POT)
    print(f"Built {src_png} -> {tex_out} & {xml_out}")


def main():
    build_framed_bigportrait()
    cn_gold = render_name_banner(
        ["葳", "丽"], [-4.5, 5.0], [-8, 12], CJK_FONT_CANDIDATES, 310, 32, gold=True
    )
    en_gold = render_name_banner(
        ["W", "I", "L", "I"], [-5.0, 4.0, -3.5, 5.5], [-10, 10, -4, 8], LATIN_FONT_CANDIDATES, 285, 16, gold=True
    )
    en_grey = render_name_banner(
        ["W", "I", "L", "I"], [-5.0, 4.0, -3.5, 5.5], [-10, 10, -4, 8], LATIN_FONT_CANDIDATES, 285, 16, gold=False
    )
    save_name_banner("names_gold_cn_wili", cn_gold)
    save_name_banner("names_gold_wili", en_gold)
    save_name_banner("names_wili", en_grey)


if __name__ == "__main__":
    main()
