"""Build the Eclipse Shiv Style-A blade-current target hit FX for all 8 lunar phases.

Run from the repository root:
    python art/tools/build_eclipse_hit_fx.py --out anim/wili_eclipse_hit_fx.zip

Requires Pillow and NumPy. Reuses eclipse_looks.py's artist-cut crystal/void
flakes and natural lunar palette, and packs all 8 phases into one single-page
KTEX atlas to prevent multi-page shader sampling flicker.
"""
from pathlib import Path
import argparse
import math
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import dst_art_pipeline as codec
from anim_draw_order import normalize_draw_order
from build_wili_scimitar_attack import serialize
from encode_ktex import encode_image, tex_info
from render_workshop_native import parse_anim

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "art/source/illustrations/weapon/eclipse-shiv"
sys.path.insert(0, str(DESIGN))
import eclipse_looks  # noqa: E402

BANK = "wili_eclipse_hit_fx"
WORK = ROOT / "art/.work"
SS = 2
FINAL_SIZE = 260
CANVAS = FINAL_SIZE * SS
CENTER = np.array([CANVAS * 0.5, CANVAS * 0.5], dtype=np.float64)
PIVOT = np.array([FINAL_SIZE * 0.5, FINAL_SIZE * 0.5], dtype=np.float64)
FPS = 30
FRAMES = 12

# Faithful to eclipse-shiv-reference.png swatches (#2A2529, #6F667A, #8EA4B5, #A7C9B3, #F2F0D1)
PHASE_STYLE = {
    "new": dict(
        primary=(38, 32, 42), primary_a=244,
        core=(146, 132, 174), core_a=180,
        glow=(76, 62, 104), glow_a=105,
        ink=(16, 13, 19), ink_a=240,
        twin=(56, 48, 66), twin_a=215,
        twin_core=(176, 162, 204), twin_core_a=135,
        flash=(170, 158, 202), flash_a=205,
        pale_ratio=0.0, shard_count=6, halo_boost=0.0, shadow_dominant=True,
    ),
    "waxing_quarter": dict(
        primary=(136, 168, 166), primary_a=235,
        core=(226, 244, 226), core_a=225,
        glow=(136, 184, 172), glow_a=105,
        ink=(24, 22, 28), ink_a=220,
        twin=(42, 36, 46), twin_a=225,
        twin_core=(132, 122, 156), twin_core_a=115,
        flash=(220, 240, 225), flash_a=225,
        pale_ratio=0.45, shard_count=7, halo_boost=0.15, shadow_dominant=False,
    ),
    "waxing_half": dict(
        primary=(176, 214, 188), primary_a=242,
        core=(244, 249, 228), core_a=245,
        glow=(156, 208, 182), glow_a=130,
        ink=(24, 26, 30), ink_a=225,
        twin=(40, 34, 44), twin_a=230,
        twin_core=(142, 134, 164), twin_core_a=120,
        flash=(238, 248, 228), flash_a=240,
        pale_ratio=0.68, shard_count=8, halo_boost=0.35, shadow_dominant=False,
    ),
    "waxing_threequarter": dict(
        primary=(192, 228, 200), primary_a=245,
        core=(248, 252, 232), core_a=250,
        glow=(168, 218, 188), glow_a=150,
        ink=(26, 30, 32), ink_a=215,
        twin=(44, 38, 48), twin_a=205,
        twin_core=(162, 178, 182), twin_core_a=120,
        flash=(245, 252, 236), flash_a=248,
        pale_ratio=0.80, shard_count=9, halo_boost=0.60, shadow_dominant=False,
    ),
    "full": dict(
        primary=(208, 240, 214), primary_a=250,
        core=(252, 254, 238), core_a=255,
        glow=(171, 224, 188), glow_a=180,
        ink=(28, 36, 36), ink_a=205,
        twin=(42, 36, 44), twin_a=200,
        twin_core=(186, 228, 202), twin_core_a=160,
        flash=(252, 255, 242), flash_a=255,
        pale_ratio=0.90, shard_count=10, halo_boost=1.0, shadow_dominant=False,
    ),
    "waning_threequarter": dict(
        primary=(168, 204, 188), primary_a=238,
        core=(234, 246, 228), core_a=235,
        glow=(140, 188, 178), glow_a=125,
        ink=(24, 24, 30), ink_a=225,
        twin=(40, 34, 44), twin_a=232,
        twin_core=(142, 132, 168), twin_core_a=130,
        flash=(224, 240, 230), flash_a=230,
        pale_ratio=0.58, shard_count=8, halo_boost=0.30, shadow_dominant=False,
    ),
    "waning_half": dict(
        primary=(40, 34, 44), primary_a=244,
        core=(160, 194, 188), core_a=205,
        glow=(106, 128, 152), glow_a=115,
        ink=(18, 15, 22), ink_a=238,
        twin=(168, 204, 190), twin_a=230,
        twin_core=(234, 246, 232), twin_core_a=225,
        flash=(204, 224, 224), flash_a=220,
        pale_ratio=0.38, shard_count=8, halo_boost=0.15, shadow_dominant=True,
    ),
    "waning_quarter": dict(
        primary=(38, 32, 42), primary_a=244,
        core=(148, 138, 182), core_a=185,
        glow=(86, 72, 122), glow_a=110,
        ink=(16, 13, 20), ink_a=238,
        twin=(118, 138, 148), twin_a=185,
        twin_core=(204, 220, 222), twin_core_a=165,
        flash=(182, 172, 212), flash_a=205,
        pale_ratio=0.20, shard_count=6, halo_boost=0.0, shadow_dominant=True,
    ),
}

SHARD_SPECS = (
    # (u_launch, lateral_off, speed, spread_deg, size_mult, delay, has_echo)
    (0.20, -20, 108, -14, 1.05, 0.04, True),
    (0.34,  18, 126,  12, 1.20, 0.06, True),
    (0.46, -28, 138, -18, 0.94, 0.07, False),
    (0.55,  24, 132,  16, 1.15, 0.07, True),
    (0.65, -16, 140,  -8, 1.02, 0.09, True),
    (0.75,  22, 118,  20, 0.88, 0.11, False),
    (0.28,  32,  96,  24, 0.80, 0.08, False),
    (0.58, -36, 116, -24, 0.86, 0.10, False),
    (0.42,  -4, 152,  -4, 1.10, 0.05, True),
    (0.80, -12, 106, -12, 0.84, 0.12, False),
)


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def paste_flake(layer, center_xy, tangent, radius, width_ratio, pale, opacity, reverse=False):
    if opacity <= 2 or radius < 1.5:
        return
    im, pivot, src, src_radius = eclipse_looks.cut_flake(pale)
    norm_t = np.linalg.norm(tangent)
    if norm_t < 1e-6:
        return
    dst = np.asarray(tangent, dtype=np.float64) / norm_t * (-1.0 if reverse else 1.0)
    perp = np.array((dst[1], -dst[0]))
    basis = np.column_stack((dst, perp))
    source = np.column_stack((src, (src[1], -src[0])))
    width = radius * width_ratio
    transform = basis @ np.diag((radius / src_radius, (width / 0.44) / src_radius)) @ source.T
    inv = np.linalg.inv(transform)
    size = int(math.ceil(radius * 2 + width * 2 + 6))
    mid = np.array((size * 0.5, size * 0.5))
    offset = pivot - inv @ mid
    warped = im.transform(
        (size, size),
        Image.Transform.AFFINE,
        (*inv[0], offset[0], *inv[1], offset[1]),
        Image.Resampling.BICUBIC,
    ).convert("RGBA")
    if opacity < 255:
        warped.putalpha(warped.getchannel("A").point(lambda a: int(a * opacity / 255.0)))
    dest = (int(round(center_xy[0] - mid[0])), int(round(center_xy[1] - mid[1])))
    layer.alpha_composite(warped, dest)


def compute_ribbon_poly(pts, widths, normal_shift=0.0):
    n = len(pts)
    if n < 3:
        return None
    left, right = [], []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        ln = np.linalg.norm(t)
        t = t / ln if ln >= 1e-6 else np.array((1.0, 0.0))
        nm = np.array((-t[1], t[0]))
        c = pts[i] + nm * normal_shift
        w = widths[i]
        left.append((float(c[0] + nm[0] * w), float(c[1] + nm[1] * w)))
        right.append((float(c[0] - nm[0] * w), float(c[1] - nm[1] * w)))
    return left + right[::-1]


def draw_calligraphic_ribbon(
    canvas,
    pts,
    base_widths,
    color,
    alpha,
    ink_color=None,
    ink_alpha=0,
    ink_pad=2.2,
    core_color=None,
    core_alpha=0,
    core_ratio=0.38,
    core_shift=0.0,
    glow_color=None,
    glow_alpha=0,
    glow_pad=6.0,
    glow_blur=6.5,
):
    if alpha <= 2 or len(pts) < 3 or np.max(base_widths) < 0.35:
        return

    if glow_color is not None and glow_alpha > 2:
        g_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        g_poly = compute_ribbon_poly(pts, base_widths + glow_pad * np.clip(base_widths / 4.0, 0.0, 1.0))
        if g_poly:
            ImageDraw.Draw(g_layer).polygon(g_poly, fill=(*glow_color, int(glow_alpha)))
            g_layer = g_layer.filter(ImageFilter.GaussianBlur(glow_blur))
            canvas.alpha_composite(g_layer)

    if ink_color is not None and ink_alpha > 2:
        i_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        pad = np.minimum(ink_pad, base_widths * 0.55 + 0.35) * np.clip(base_widths / 1.2, 0.0, 1.0)
        i_poly = compute_ribbon_poly(pts, base_widths + pad)
        if i_poly:
            ImageDraw.Draw(i_layer).polygon(i_poly, fill=(*ink_color, int(ink_alpha)))
            canvas.alpha_composite(i_layer)

    b_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    b_poly = compute_ribbon_poly(pts, base_widths)
    if b_poly:
        ImageDraw.Draw(b_layer).polygon(b_poly, fill=(*color, int(alpha)))
        canvas.alpha_composite(b_layer)

    if core_color is not None and core_alpha > 2:
        c_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        c_widths = base_widths * core_ratio
        c_poly = compute_ribbon_poly(pts, c_widths, normal_shift=core_shift)
        if c_poly:
            ImageDraw.Draw(c_layer).polygon(c_poly, fill=(*core_color, int(core_alpha)))
            canvas.alpha_composite(c_layer)


def draw_impact_star(canvas, center_xy, angle_rad, length, width, color, alpha, glow_color=None, glow_alpha=0):
    if alpha <= 2 or length < 2 or width < 0.6:
        return
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    u = np.array((c, s))
    v = np.array((-s, c))
    pts = [
        tuple(center_xy + u * length),
        tuple(center_xy + v * width),
        tuple(center_xy - u * length),
        tuple(center_xy - v * width),
    ]
    if glow_color is not None and glow_alpha > 2:
        gl = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        g_pts = [
            tuple(center_xy + u * (length * 1.15)),
            tuple(center_xy + v * (width * 1.85)),
            tuple(center_xy - u * (length * 1.15)),
            tuple(center_xy - v * (width * 1.85)),
        ]
        ImageDraw.Draw(gl).polygon(g_pts, fill=(*glow_color, int(glow_alpha)))
        gl = gl.filter(ImageFilter.GaussianBlur(5.5))
        canvas.alpha_composite(gl)
    fl = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(fl).polygon(pts, fill=(*color, int(alpha)))
    canvas.alpha_composite(fl)


def arc_slash_point(s, radius, bulge, rot_rad, offset_xy=(0.0, 0.0)):
    lx = (0.5 - s) * 2.0 * radius
    ly = (0.48 - math.sin(math.pi * s)) * bulge
    c, sn = math.cos(rot_rad), math.sin(rot_rad)
    gx = lx * c - ly * sn + CENTER[0] + offset_xy[0]
    gy = lx * sn + ly * c + CENTER[1] + offset_xy[1]
    return np.array((gx, gy), dtype=np.float64)


def render_hit_frame(phase_id, frame_idx):
    st = PHASE_STYLE[phase_id]
    p = frame_idx / (FRAMES - 1)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    rot = math.radians(-32.0)

    def sample_arc_ribbon(
        u_tail, u_head, radius, bulge, max_w, sway_amp, sway_freq, offset_xy, n_pts=64
    ):
        u0 = max(0.0, min(1.0, u_tail))
        u1 = max(0.0, min(1.0, u_head))
        span = u1 - u0
        if span < 0.04:
            return None, None
        us = np.linspace(u0, u1, n_pts)
        raw = np.array([arc_slash_point(u, radius, bulge, rot, offset_xy) for u in us])
        pts = np.zeros_like(raw)
        widths = np.zeros(n_pts, dtype=np.float64)
        span_scale = min(1.0, span / 0.55) ** 0.85
        time_thin = 1.0 - 0.72 * (p ** 1.35)
        eff_sway = sway_amp * min(1.0, span / 0.50)
        for i, u in enumerate(us):
            frac = i / (n_pts - 1)
            t = raw[min(n_pts - 1, i + 1)] - raw[max(0, i - 1)]
            ln = np.linalg.norm(t)
            nm = np.array((-t[1], t[0])) / max(ln, 1e-6)
            sway = eff_sway * math.sin(sway_freq * math.pi * u - p * 8.0) * math.sin(math.pi * frac)
            pts[i] = raw[i] + nm * sway
            taper = (frac ** 1.08) * ((1.0 - frac) ** 0.44) / (0.71 ** 1.08 * 0.29 ** 0.44)
            ripple = 1.0 + 0.12 * math.sin(4.0 * math.pi * frac + p * 5.0)
            widths[i] = max(0.0, max_w * span_scale * time_thin * taper * ripple)
        return pts, widths

    ribbon_env = smoothstep(p / 0.10) * (1.0 - smoothstep((p - 0.54) / 0.46))

    # 1. Secondary twin counter-ribbon
    t_head = min(1.0, 0.18 + 0.82 * ((p / 0.44) ** 0.72))
    t_tail = max(0.0, (p - 0.12) / 0.80) ** 1.15
    pts2, w2 = sample_arc_ribbon(
        t_tail, t_head, radius=192.0, bulge=64.0, max_w=11.5,
        sway_amp=8.0, sway_freq=3.2, offset_xy=(-8.0, 18.0),
    )
    if pts2 is not None:
        draw_calligraphic_ribbon(
            canvas, pts2, w2,
            color=st["twin"], alpha=st["twin_a"] * ribbon_env,
            ink_color=st["ink"], ink_alpha=st["ink_a"] * 0.88 * ribbon_env, ink_pad=2.0,
            core_color=st["twin_core"], core_alpha=st["twin_core_a"] * ribbon_env,
            core_ratio=0.30, core_shift=-1.6,
            glow_color=st["glow"], glow_alpha=st["glow_a"] * 0.42 * ribbon_env,
            glow_pad=4.5, glow_blur=5.5,
        )

    # 2. Primary crescent blade-current ribbon
    m_head = min(1.0, 0.24 + 0.76 * ((p / 0.34) ** 0.65))
    m_tail = max(0.0, (p - 0.08) / 0.78) ** 1.20
    pts1, w1 = sample_arc_ribbon(
        m_tail, m_head, radius=216.0, bulge=78.0, max_w=18.5 + 3.0 * st["halo_boost"],
        sway_amp=4.8 if not st["shadow_dominant"] else 7.8,
        sway_freq=2.8 if not st["shadow_dominant"] else 3.6,
        offset_xy=(0.0, 0.0),
    )
    if pts1 is not None:
        draw_calligraphic_ribbon(
            canvas, pts1, w1,
            color=st["primary"], alpha=st["primary_a"] * ribbon_env,
            ink_color=st["ink"], ink_alpha=st["ink_a"] * ribbon_env, ink_pad=2.5,
            core_color=st["core"], core_alpha=st["core_a"] * ribbon_env,
            core_ratio=0.38, core_shift=2.6,
            glow_color=st["glow"], glow_alpha=(st["glow_a"] + 50 * st["halo_boost"]) * ribbon_env,
            glow_pad=8.0 + 4.5 * st["halo_boost"], glow_blur=7.5 + 2.5 * st["halo_boost"],
        )

    # 3. Outer & lower razor wind-shear filaments
    wind_env = smoothstep(p / 0.08) * (1.0 - smoothstep((p - 0.44) / 0.48))
    w_head = min(1.0, 0.28 + 0.72 * ((p / 0.32) ** 0.60))
    w_tail = max(0.0, (p - 0.05) / 0.70) ** 1.08
    pts3, w3 = sample_arc_ribbon(
        w_tail, w_head, radius=228.0, bulge=94.0, max_w=4.4,
        sway_amp=4.0, sway_freq=3.8, offset_xy=(5.0, -14.0),
    )
    if pts3 is not None:
        draw_calligraphic_ribbon(
            canvas, pts3, w3,
            color=st["core"], alpha=st["core_a"] * 0.85 * wind_env,
            ink_color=st["ink"], ink_alpha=st["ink_a"] * 0.60 * wind_env, ink_pad=1.2,
            glow_color=st["glow"], glow_alpha=st["glow_a"] * 0.45 * wind_env,
            glow_pad=3.5, glow_blur=4.0,
        )

    w4_head = min(1.0, 0.14 + 0.86 * ((p / 0.46) ** 0.75))
    w4_tail = max(0.0, (p - 0.16) / 0.76) ** 1.12
    pts4, w4 = sample_arc_ribbon(
        w4_tail, w4_head, radius=176.0, bulge=46.0, max_w=5.0,
        sway_amp=6.5, sway_freq=3.5, offset_xy=(4.0, 26.0),
    )
    if pts4 is not None:
        draw_calligraphic_ribbon(
            canvas, pts4, w4,
            color=st["twin"] if not st["shadow_dominant"] else st["core"],
            alpha=(st["twin_a"] if not st["shadow_dominant"] else st["core_a"] * 0.75) * wind_env,
            ink_color=st["ink"], ink_alpha=st["ink_a"] * 0.65 * wind_env, ink_pad=1.2,
        )

    # 4. Crisp impact rift flash at center
    if p < 0.34:
        fp = p / 0.34
        f_alpha = 1.0 - fp ** 1.4
        draw_impact_star(
            canvas, CENTER, rot,
            length=122.0 * (0.45 + 0.62 * smoothstep(fp * 2.4)),
            width=10.5 * (1.0 - 0.68 * fp),
            color=st["flash"], alpha=st["flash_a"] * f_alpha,
            glow_color=st["glow"], glow_alpha=st["glow_a"] * 0.9 * f_alpha,
        )
        draw_impact_star(
            canvas, CENTER, rot + math.radians(78.0),
            length=46.0 * (0.5 + 0.5 * fp),
            width=5.5 * (1.0 - 0.72 * fp),
            color=st["core"], alpha=st["core_a"] * 0.85 * f_alpha,
        )

    # 5. Artist-cut moon crystal lozenges & void scales
    count = st["shard_count"]
    pale_n = round(count * st["pale_ratio"])
    for idx in range(count):
        u0, lat, speed, spread_deg, sz_m, delay, has_echo = SHARD_SPECS[idx]
        if p < delay:
            continue
        sp = min(1.0, (p - delay) / (1.0 - delay))
        travel = 1.0 - (1.0 - sp) ** 2.35
        base_pt = arc_slash_point(u0, 210.0, 74.0, rot)
        nxt_pt = arc_slash_point(min(1.0, u0 + 0.02), 210.0, 74.0, rot)
        tan = nxt_pt - base_pt
        tan = tan / max(np.linalg.norm(tan), 1e-6)
        nm = np.array((-tan[1], tan[0]))
        ca, sa = math.cos(math.radians(spread_deg)), math.sin(math.radians(spread_deg))
        vel_dir = np.array((tan[0] * ca - tan[1] * sa, tan[0] * sa + tan[1] * ca))
        pos = base_pt + nm * lat + vel_dir * (speed * travel)
        fade = smoothstep(sp / 0.14) * (1.0 - smoothstep((sp - 0.56) / 0.44))
        pale = idx < pale_n
        rad = (15.5 + 4.0 * st["halo_boost"]) * sz_m * (0.72 + 0.28 * (1.0 - 0.35 * sp))
        paste_flake(canvas, pos, vel_dir, rad, 0.45 if pale else 0.42, pale, round(248 * fade), reverse=False)
        if has_echo and sp < 0.78:
            for z in (1, 2):
                echo_pos = pos - vel_dir * (z * 11.0 + rad * 0.85)
                paste_flake(
                    canvas, echo_pos, vel_dir,
                    rad * (0.44 / z), 0.22 / z + 0.18,
                    pale, round(155 * fade / z), reverse=False,
                )

    return canvas.resize((FINAL_SIZE, FINAL_SIZE), Image.Resampling.LANCZOS)


def build_assets():
    symbols, clips, tiles = [], [], {}
    names = {codec.hash_name(BANK): BANK}

    for phase in eclipse_looks.PHASES:
        sym_name = f"hit_slash_{phase}"
        sym_hash = codec.hash_name(sym_name)
        names[sym_hash] = sym_name
        build_frames = []
        boxes = []
        timeline_elems = []
        for i in range(FRAMES):
            im = render_hit_frame(phase, i)
            rect = im.getchannel("A").getbbox()
            if rect is None:
                timeline_elems.append([])
                continue
            l, t, r, b = rect
            tile_name = f"{phase}_{i}"
            tiles[tile_name] = im.crop(rect)
            cx = (l + r) * 0.5 - PIVOT[0]
            cy = (t + b) * 0.5 - PIVOT[1]
            w, h = float(r - l), float(b - t)
            build_frames.append(dict(frame=i, duration=1, x=cx, y=cy, w=w, h=h, png=tile_name))
            boxes.append((cx, cy, w, h))
            timeline_elems.append([dict(symbol=sym_hash, layer=sym_hash, frame=i, matrix=[1, 0, 0, 1, 0, 0, -5])])
        # Append one empty end frame so animover cleanly clears before Remove().
        timeline_elems.append([])
        symbols.append(dict(name=sym_name, hash=sym_hash, frames=build_frames))
        left = min(x - w * 0.5 for x, y, w, h in boxes)
        right = max(x + w * 0.5 for x, y, w, h in boxes)
        top = min(y - h * 0.5 for x, y, w, h in boxes)
        bottom = max(y + h * 0.5 for x, y, w, h in boxes)
        bbox = [(left + right) * 0.5, (top + bottom) * 0.5, right - left, bottom - top]
        anim_frames = [
            normalize_draw_order(dict(bbox=bbox, events=[], elements=els))
            for els in timeline_elems
        ]
        clips.append(dict(name=f"hit_{phase}", root=codec.hash_name(BANK), facing=255, fps=FPS, frames=anim_frames))

    # Pack into a single power-of-two atlas to guarantee zero multi-page shader flicker.
    side = 2048
    padding = 4
    placements = {}
    pages = [[]]
    extents = [[0, 0]]
    x = y = padding
    row = 0
    for name, im in sorted(tiles.items(), key=lambda t: (-t[1].height, -t[1].width, t[0])):
        if x + im.width + padding > side:
            x, y, row = padding, y + row + 2 * padding, 0
        if y + im.height + padding > side:
            pages.append([])
            extents.append([0, 0])
            x = y = padding
            row = 0
        pages[-1].append((name, x, y))
        ex = extents[-1]
        ex[0] = max(ex[0], x + im.width + padding)
        ex[1] = max(ex[1], y + im.height + padding)
        x += 4 * math.ceil((im.width + 2 * padding) / 4)
        row = max(row, 4 * math.ceil(im.height / 4))
    if len(pages) != 1:
        raise ValueError("Eclipse hit FX must fit in one atlas to prevent shader page flicker")

    items, extent = pages[0], extents[0]
    aw, ah = (1 << (s - 1).bit_length() for s in extent)
    atlas = Image.new("RGBA", (aw, ah))
    for name, px, py in items:
        im = tiles[name]
        atlas.paste(im, (px, py))
        placements[name] = dict(x=px, y=py, w=im.width, h=im.height, aw=aw, ah=ah, page=0)

    tex_bytes = encode_image(atlas)
    tex_info(tex_bytes)
    symbols.sort(key=lambda s: s["hash"])
    build_bytes = codec.serialize_build(dict(name=BANK, symbols=symbols), ["atlas-0.tex"], placements)
    anim_bytes = serialize(clips, names)
    parse_anim(anim_bytes)
    return {"atlas-0.tex": tex_bytes, "build.bin": build_bytes, "anim.bin": anim_bytes, "_atlas_size": (aw, ah)}


def build_archive(out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    assets = build_assets()
    atlas_size = assets.pop("_atlas_size")
    with ZipFile(out, "w") as archive:
        for name, data in assets.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            archive.writestr(info, data, compress_type=ZIP_DEFLATED)
    print(f"{out} ({out.stat().st_size:,} bytes, single atlas {atlas_size[0]}x{atlas_size[1]})")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, default=WORK / (BANK + ".zip"))
    args = cli.parse_args()
    build_archive(args.out)
