#!/usr/bin/env python3
"""Build anim/wili_eye_anim.zip using clean generated hand-inked eye layers for silky-smooth gaze & blink animation.

Source layers in art/source/anim/wili/eye_anim/:
- front_empty_sclera.png, front_blink_1.png, front_blink_2.png, front_blink_3.png (locked to symmetric face-10)
- side_empty_sclera.png, side_blink_1.png, side_blink_2.png, side_blink_3.png (locked to face-4)

Emits 8 symbols on a single 2048x1024 BC3 atlas:
- 5 smooth horizontal gaze steps (0% eye-shape compression):
    face_look_left, face_mid_left, face_center, face_mid_right, face_look_right
- 3 hand-drawn eyelid blink stages (45% -> 78% -> 100% closed):
    face_blink_1, face_blink_2, face_blink_3

All non-neutral expression frames (2, 6..14: hurt, death, lunacy, talking, sleep) are preserved verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "art/tools"))

import dst_art_pipeline as codec
from encode_ktex import encode_image

WILI_BUILD = ROOT / "art/source/anim/wili/build.json"
WILI_SPRITES = ROOT / "art/source/anim/wili/sprites"
EYE_SRC = ROOT / "art/source/anim/wili/eye_anim"
BANK = "wili_eye_anim"
DEFAULT_OUT = ROOT / "anim" / f"{BANK}.zip"


def _find_sclera_regions(empty_im: Image.Image) -> list[dict]:
    """Find the exact white+cel-shadow eye opening(s) inside a clean hand-drawn empty-sclera sprite."""
    arr = np.asarray(empty_im, dtype=np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3]
    lum = rgb @ np.array((0.299, 0.587, 0.114), dtype=np.float32)
    # In an empty-sclera plate there is NO iris at all: interior pixels are simply bright white/gray (lum > 135)
    # completely enclosed inside solid jet-black eyelids!
    opening = (a > 210) & (lum > 135)
    h, w = opening.shape

    # Split into left/right eye (front) or single eye (side) via connected components
    visited = np.zeros((h, w), dtype=bool)
    comps = []
    for y in range(h):
        for x in range(w):
            if opening[y, x] and not visited[y, x]:
                stack = [(y, x)]
                visited[y, x] = True
                pts = []
                while stack:
                    cy, cx = stack.pop()
                    pts.append((cy, cx))
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and opening[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if len(pts) >= 120:
                    m = np.zeros((h, w), dtype=bool)
                    ys, xs = zip(*pts)
                    m[ys, xs] = True
                    # Soft 0.45px inner anti-alias mask strictly inside the black eyelids (never touches eyelid ink!)
                    soft = np.asarray(
                        Image.fromarray(np.uint8(m * 255)).filter(ImageFilter.GaussianBlur(0.45)),
                        dtype=np.float32,
                    ) / 255.0
                    # Keep mask strictly inside opaque eye pixels & clip faint bleed onto solid black lashes
                    soft = np.where(lum > 70, soft, 0.0)
                    # Measure per-column bottom of the sclera opening so iris tracks the natural lower eyelid curve
                    bot_y = np.full(w, np.nan, dtype=np.float32)
                    for col in range(min(xs), max(xs) + 1):
                        cys = np.where(m[:, col])[0]
                        if len(cys):
                            bot_y[col] = float(cys[-1])
                    comps.append({
                        "x0": int(min(xs)),
                        "x1": int(max(xs)),
                        "y0": int(min(ys)),
                        "y1": int(max(ys)),
                        "cx": float(np.mean(xs)),
                        "bot_y": bot_y,
                        "mask": soft,
                    })
    comps.sort(key=lambda d: d["cx"])
    return comps


def _extract_artist_iris(src_im: Image.Image, eye_index: int = 0) -> tuple[Image.Image, tuple[float, float]]:
    """Extract the original artist's unobstructed hand-drawn iris+pupil+border from face-10.png."""
    arr = np.asarray(src_im, dtype=np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3]
    lum = rgb @ np.array((0.299, 0.587, 0.114), dtype=np.float32)
    bdiff = rgb[:, :, 2] - rgb[:, :, 0]
    iris_blue = (a > 180) & (bdiff > 9) & (lum > 35) & (lum < 215)

    h, w = iris_blue.shape
    mid = w // 2
    sub = iris_blue[:, :mid] if eye_index == 0 else iris_blue[:, mid:]
    iy, ix = np.where(sub)
    x_off = 0 if eye_index == 0 else mid
    ix_min, ix_max = x_off + int(ix.min()), x_off + int(ix.max())
    iy_min, iy_max = int(iy.min()), int(iy.max())

    px0, px1 = ix_min - 4, ix_max + 5
    py0, py1 = iy_min - 8, iy_max + 4
    patch = arr[py0:py1, px0:px1].copy()
    ph, pw = patch.shape[:2]

    p_rgb = patch[:, :, :3]
    p_lum = p_rgb @ np.array((0.299, 0.587, 0.114), dtype=np.float32)
    p_bdiff = p_rgb[:, :, 2] - p_rgb[:, :, 0]
    p_blue = (patch[:, :, 3] > 180) & (p_bdiff > 9) & (p_lum > 35) & (p_lum < 215)
    by, bx = np.where(p_blue)

    cx = 0.5 * (float(bx.min()) + float(bx.max()))
    rx = 0.5 * (float(bx.max()) - float(bx.min())) + 2.4
    bot_edge = float(by.max()) + 2.1
    ry = rx * 1.08
    cy = bot_edge - ry

    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    oval_a = np.clip((1.03 - r) / 0.10, 0.0, 1.0)
    not_sclera = np.clip((195.0 - p_lum) / 35.0, 0.0, 1.0)
    is_blue = np.clip((p_bdiff - 6.0) / 8.0, 0.0, 1.0)
    fg = np.maximum(not_sclera, is_blue)

    out = patch.copy()
    upper_in = (yy < by.min() + 3.0) & (r < 0.90) & (p_bdiff < 10) & (p_lum > 45)
    out[upper_in, :3] = np.array((8.0, 9.0, 12.0), dtype=np.float32)
    out[:, :, 3] = np.clip(oval_a * np.maximum(fg, upper_in.astype(np.float32)) * 255.0, 0.0, 255.0)
    rim_fix = (r >= 0.84) & (r <= 1.04) & (p_lum > 130) & (p_bdiff < 12)
    out[rim_fix, :3] = np.array((8.0, 8.0, 10.0), dtype=np.float32)

    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGBA"), (cx, bot_edge)


def _render_gaze_frame(
    empty_im: Image.Image,
    regions: list[dict],
    iris_patches: list[tuple[Image.Image, tuple[float, float]]],
    shift_px: float,
    x_scale: float = 1.0,
) -> Image.Image:
    """Composite crisp artist iris(es) into clean empty_im at sub-pixel horizontal offset shift_px."""
    arr = np.asarray(empty_im, dtype=np.float32).copy()
    h, w = arr.shape[:2]

    for i, reg in enumerate(regions):
        patch_im, (pcx, pbot) = iris_patches[min(i, len(iris_patches) - 1)]
        if abs(x_scale - 1.0) > 1e-3:
            nw = max(4, int(round(patch_im.width * x_scale)))
            patch_im = patch_im.resize((nw, patch_im.height), Image.Resampling.LANCZOS)
            pcx = pcx * x_scale

        # Subtle natural binocular convergence on front center (matching face-10!)
        conv = (1.5 if i == 0 else -1.5) if len(regions) == 2 else 2.5
        target_cx = 0.5 * (reg["x0"] + reg["x1"]) + conv + shift_px

        # Track the smooth lower-eyelid curve at target_cx so iris never floats or drops below the lower lash
        col_c = int(np.clip(round(target_cx), reg["x0"], reg["x1"]))
        local_bot = float(reg["bot_y"][col_c]) if not np.isnan(reg["bot_y"][col_c]) else float(reg["y1"])
        target_bot = local_bot - 0.6

        # Sub-pixel translation via PIL AFFINE so mid_left / mid_right steps glide with silky precision!
        tx = target_cx - pcx
        ty = target_bot - pbot
        layer = patch_im.transform(
            (w, h),
            Image.Transform.AFFINE,
            (1.0, 0.0, -tx, 0.0, 1.0, -ty),
            Image.Resampling.BICUBIC,
        )
        la = np.asarray(layer, dtype=np.float32)
        alpha = (la[:, :, 3] / 255.0) * reg["mask"]
        arr[:, :, :3] = arr[:, :, :3] * (1.0 - alpha[..., None]) + la[:, :, :3] * alpha[..., None]

    return Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8), "RGBA")


def build_face_variants():
    """Return (tiles, symbols) for 8 silky-smooth face override symbols (5 gaze + 3 blink)."""
    base_build = json.loads(WILI_BUILD.read_text(encoding="utf-8"))
    face_sym = next(s for s in base_build["symbols"] if s["name"] == "face")
    base_frames = {f["frame"]: dict(f) for f in face_sym["frames"]}

    tiles = {}
    for idx in sorted(base_frames):
        tiles[f"orig_{idx}"] = Image.open(WILI_SPRITES / f"face-{idx}.png").convert("RGBA")

    # Load generated hand-inked layers (symmetric face-10 front & face-4 side)
    front_empty = Image.open(EYE_SRC / "front_empty_sclera.png").convert("RGBA")
    side_empty = Image.open(EYE_SRC / "side_empty_sclera.png").convert("RGBA")
    front_regs = _find_sclera_regions(front_empty)
    side_regs = _find_sclera_regions(side_empty)

    iris_L = _extract_artist_iris(tiles["orig_10"], 0)
    iris_R = _extract_artist_iris(tiles["orig_10"], 1)

    # 5 silky horizontal gaze frames for BOTH front (locked symmetric face-10 outline) & side (locked face-4 outline)
    gaze_specs = [
        ("look_left", -10.5, -8.5),
        ("mid_left", -5.25, -4.5),
        ("center", 0.0, -0.5),
        ("mid_right", 5.25, 2.5),
        ("look_right", 10.5, 5.2),
    ]
    for tag, f_dx, s_dx in gaze_specs:
        tiles[f"f_{tag}"] = _render_gaze_frame(front_empty, front_regs, [iris_L, iris_R], shift_px=f_dx, x_scale=1.0)
        tiles[f"s_{tag}"] = _render_gaze_frame(side_empty, side_regs, [iris_L], shift_px=s_dx, x_scale=0.72)

    # 3 hand-drawn eyelid blink stages (45% -> 78% -> 100% closed)
    for k in (1, 2, 3):
        tiles[f"f_blink_{k}"] = Image.open(EYE_SRC / f"front_blink_{k}.png").convert("RGBA")
        tiles[f"s_blink_{k}"] = Image.open(EYE_SRC / f"side_blink_{k}.png").convert("RGBA")

    # Geometry matching face-10 (front, aligned to face-0 baseline) and face-4 (side)
    f10 = base_frames[10]
    g_front = {"x": f10["x"] - 0.6, "y": f10["y"] + 0.3, "w": f10["w"], "h": f10["h"]}
    f4 = base_frames[4]
    g_side = {"x": f4["x"], "y": f4["y"], "w": f4["w"], "h": f4["h"]}

    def make_symbol_frames(f_tile: str, s_tile: str, override_side5: bool = False):
        frames = []
        for idx in sorted(base_frames):
            fr = dict(base_frames[idx])
            if idx in (0, 1, 3):
                fr.update(g_front)
                fr["png"] = f_tile
            elif idx == 4 or (override_side5 and idx == 5):
                fr.update(g_side)
                fr["png"] = s_tile
            else:
                fr["png"] = f"orig_{idx}"
            frames.append(fr)
        return frames

    specs = [
        ("face_look_left", "f_look_left", "s_look_left", False),
        ("face_mid_left", "f_mid_left", "s_mid_left", False),
        ("face_center", "f_center", "s_center", False),
        ("face_mid_right", "f_mid_right", "s_mid_right", False),
        ("face_look_right", "f_look_right", "s_look_right", False),
        ("face_blink_1", "f_blink_1", "s_blink_1", True),
        ("face_blink_2", "f_blink_2", "s_blink_2", True),
        ("face_blink_3", "f_blink_3", "s_blink_3", True),
    ]
    symbols = [
        {"name": name, "hash": codec.hash_name(name), "frames": make_symbol_frames(ft, st, s5)}
        for name, ft, st, s5 in specs
    ]
    symbols.sort(key=lambda s: s["hash"])
    return tiles, symbols


def build_archive(out: Path = DEFAULT_OUT) -> Path:
    tiles, symbols = build_face_variants()

    padding = 4
    side = 2048
    x = y = padding
    row_h = 0
    placements = {}
    ext_w = ext_h = 0
    for name, im in sorted(tiles.items(), key=lambda t: (-t[1].height, -t[1].width, t[0])):
        if x + im.width + padding > side:
            x, y, row_h = padding, y + row_h + 2 * padding, 0
        placements[name] = {"page": 0, "x": x, "y": y, "w": im.width, "h": im.height}
        ext_w = max(ext_w, x + im.width + padding)
        ext_h = max(ext_h, y + im.height + padding)
        x += 4 * math.ceil((im.width + 2 * padding) / 4)
        row_h = max(row_h, 4 * math.ceil(im.height / 4))
    aw = 1 << (ext_w - 1).bit_length()
    ah = 1 << (ext_h - 1).bit_length()
    atlas = Image.new("RGBA", (aw, ah))
    for name, p in placements.items():
        p["aw"], p["ah"] = aw, ah
        atlas.paste(tiles[name], (p["x"], p["y"]))

    atlas_bytes = encode_image(atlas)
    build_bytes = codec.serialize_build({"name": BANK, "symbols": symbols}, ["atlas-0.tex"], placements)
    check = codec.parse_build(build_bytes)
    assert check["symbol_count"] == len(symbols)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out, "w") as zf:
        for fname, payload in (("atlas-0.tex", atlas_bytes), ("build.bin", build_bytes)):
            info = ZipInfo(fname, (1980, 1, 1, 0, 0, 0))
            zf.writestr(info, payload, compress_type=ZIP_DEFLATED)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"Built {out} ({out.stat().st_size:,} bytes, atlas={aw}x{ah}, symbols={len(symbols)}, sha256={sha[:12]}...)")
    return out


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = cli.parse_args()
    build_archive(args.out)
