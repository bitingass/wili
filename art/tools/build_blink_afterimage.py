"""Bake Wili's directional blink silhouettes from the current mod assets.

Run from the repository: python art/tools/build_blink_afterimage.py
Requires Pillow and NumPy. Reads the current Wili builds and private attack
clips, and writes one standalone ANIM/BILD/KTEX archive to art/.work.
"""
import argparse
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
from PIL import Image

import render_workshop_native as rig
from build_wili_scimitar_attack import serialize
from dst_art_pipeline import hash_name, serialize_build
from encode_ktex import encode_image


BANK = "wili_blink_afterimage"
ALPHAS = (0.76, 0.58, 0.40, 0.24, 0.10)
FACINGS = (8, 5, 2)  # Front, left/right shared via the game's horizontal flip, back.
ORIGIN = (450, 880)
SCALE = 2.0


def render_pose(clip, facing, weapon, body, swap, names):
    anim = next(a for a in clip if a["name"] == "wili_scimitar_atk" and a["facing"] == facing)
    overrides = {"swap_object": (swap, hash_name("swap_spear"))} if weapon else {}
    absent = {text for key, text in names.items() if key not in body and text not in overrides}
    frame, missing = rig.render_frame(
        anim["frames"][9], body, names, size=(1000, 1000), origin=ORIGIN, scale=SCALE,
        hide_layers=("ARM_normal", "HEAD_HAT", "HAIR_HAT", "HAT"),
        hide_symbols=absent, overrides=overrides,
    )
    if missing:
        raise ValueError(f"Unresolved blink pose parts: {missing}")
    left, top, right, bottom = frame.getbbox()
    if min(left, top) == 0 or right == frame.width or bottom == frame.height:
        raise ValueError("Blink pose reached its staging canvas edge")
    width = (right - left) / SCALE
    height = (bottom - top) / SCALE
    bbox = [((left + right) / 2 - ORIGIN[0]) / SCALE, ((top + bottom) / 2 - ORIGIN[1]) / SCALE,
            width, height]
    # Samples approach 1 texel per framebuffer pixel at typical game zoom.
    frame = frame.crop((left, top, right, bottom)).resize(
        (round(width * 0.625), round(height * 0.625)), Image.Resampling.LANCZOS
    )
    return moon_ink(frame), bbox


def moon_ink(sprite):
    rgba = np.asarray(sprite)
    # A narrow sapphire ramp preserves the face, forelock and knife as shapes.
    # The ghost stays translucent and takes the scene lighting normally.
    lum = np.asarray(sprite.convert("L"))
    ramp = np.array([[41, 65, 107], [70, 116, 173], [115, 165, 217], [179, 213, 243]])
    stops = (0, 55, 140, 255)
    result = np.empty_like(rgba)
    for channel in range(3):
        result[:, :, channel] = np.interp(lum, stops, ramp[:, channel])
    result[:, :, 3] = rgba[:, :, 3]
    return Image.fromarray(result)


def make_assets():
    body = rig.frame_lookup(rig.source_build("wili"))
    swap = rig.frame_lookup(rig.source_build("swap_scimitar"))
    bank = rig.anim_archive("wili_scimitar_attack.zip", rig.PROJECT / "anim")
    poses = []
    for name in ("blink", "blink_scimitar"):
        for facing in FACINGS:
            image, bbox = render_pose(bank["anims"], facing, name == "blink_scimitar", body, swap, bank["names"])
            poses.append((name, facing, image, bbox))
    padding = 5
    cell_width = max(im.width for _, _, im, _ in poses) + 2 * padding
    cell_height = max(im.height for _, _, im, _ in poses) + 2 * padding
    aw = 2 ** math.ceil(math.log2(len(poses) * cell_width))
    ah = 2 ** math.ceil(math.log2(len(ALPHAS) * cell_height))
    atlas = Image.new("RGBA", (aw, ah))
    symbols, clips, placements = [], [], {}
    names = {hash_name(BANK): BANK}
    for column, (name, facing, sprite, bbox) in enumerate(poses):
        symbol = f"{BANK}_{name}_{facing}"
        key = hash_name(symbol)
        names[key] = symbol
        build_frames, timeline = [], []
        for i, opacity in enumerate(ALPHAS):
            x, y = column * cell_width + padding, i * cell_height + padding
            shaded = sprite.copy()
            shaded.putalpha(sprite.getchannel("A").point(lambda a: round(a * opacity)))
            atlas.paste(shaded, (x, y))
            tile = f"{symbol}_{i}"
            placements[tile] = dict(page=0, x=x, y=y, w=sprite.width, h=sprite.height, aw=aw, ah=ah)
            build_frames.append(dict(frame=i, duration=1, x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3], png=tile))
            element = dict(symbol=key, layer=key, frame=i, matrix=[1, 0, 0, 1, 0, 0, -5])
            timeline.append(dict(bbox=bbox, events=[], elements=[element]))
        timeline.append(dict(bbox=bbox, events=[], elements=[]))
        symbols.append(dict(name=symbol, hash=key, frames=build_frames))
        clips.append(dict(name=name, facing=facing, root=hash_name(BANK), fps=30, frames=timeline))
    # BILD symbols are conventionally ordered by their unsigned hashes.
    symbols.sort(key=lambda s: s["hash"])
    build = dict(name=BANK, symbols=symbols)
    return {"build.bin": serialize_build(build, ["atlas-0.tex"], placements),
            "anim.bin": serialize(clips, names), "atlas-0.tex": encode_image(atlas)}


def build_archive(out):
    assets = make_assets()
    out.parent.mkdir(exist_ok=True, parents=True)
    with ZipFile(out, "w") as packed:
        for name, data in assets.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            packed.writestr(info, data, compress_type=ZIP_DEFLATED)
    print(f"{out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=rig.PROJECT / "art/.work" / (BANK + ".zip"))
    build_archive(parser.parse_args().out)
