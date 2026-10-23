"""Recover clipped head tips from the existing illustration, without moving the rig.

Outputs a reviewable source/build/runtime patch under art/.work/head-tip-fix.
Only the last four resampling rows and missing tips are replaced. Other pixels,
symbols, and the original compressed atlas are preserved.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import zipfile

from PIL import Image

import dst_art_pipeline as codec
from encode_ktex import encode_tex

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("art/source/anim/wili")
ATLAS = "atlas-head-tips.tex"


def serialize(build):
    """Keep the existing v6 topology/UVs for every unaffected symbol."""
    data = bytearray()

    def write(fmt, *values):
        data.extend(struct.pack("<" + fmt, *values))

    def string(value):
        encoded = value.encode("utf-8")
        write("I", len(encoded))
        data.extend(encoded)

    write("4sIII", b"BILD", 6, len(build["symbols"]), build["frame_count"])
    string(build["name"])
    write("I", len(build["atlases"]))
    for name in build["atlases"]:
        string(name)
    for symbol in build["symbols"]:
        write("II", symbol["hash"], len(symbol["frames"]))
        for frame in symbol["frames"]:
            write("IIffffII", *(frame[k] for k in
                  ("frame", "duration", "x", "y", "w", "h", "vertex_start", "vertex_count")))
    write("I", len(build["vertices"]))
    for vertex in build["vertices"]:
        write("ffffff", *vertex)
    write("I", len(build["stored_names"]))
    for key, name in build["stored_names"].items():
        write("I", key)
        string(name)
    return bytes(data)


def restore(output):
    recipe = json.loads((ROOT / SOURCE / "head-slices.json").read_text())
    illustration = Image.open(ROOT / recipe["source"]).convert("RGBA")
    source_build = json.loads((ROOT / SOURCE / "build.json").read_text())
    frames = {f["frame"]: f for s in source_build["symbols"]
              if s["name"] == "headbase" for f in s["frames"]}
    sprites = {}
    for record in recipe["frames"]:
        frame = frames[record["frame"]]
        old = Image.open(ROOT / SOURCE / "sprites" / frame["png"]).convert("RGBA")
        cw, ch = record["original_canvas"]
        extra = record["restore_rows"]
        if old.size not in ((cw, ch), (cw, ch + extra)):
            raise ValueError(f"Unexpected canvas for {frame['png']}: {old.size}")
        left, top, right, bottom = record["source_crop"]
        width, height = record["resized_size"]
        new_height = height + extra
        # Fractional source extent keeps exactly the original scale/pixel origin.
        source_height = new_height * (bottom - top) / height
        crop = illustration.crop((left, top, right, top + math.ceil(source_height)))
        restored = crop.resize((width, new_height), Image.Resampling.LANCZOS,
                              box=(0, 0, right - left, source_height))
        x, y = record["paste_at"]
        join = height - 4  # Recompute the filter footprint at the former cut edge.
        sprite = Image.new("RGBA", (cw, ch + extra))
        sprite.paste(old.crop((0, 0, cw, y + join)), (0, 0))
        sprite.paste(restored.crop((0, join, width, new_height)), (x, y + join))
        target = output / SOURCE / "sprites" / frame["png"]
        target.parent.mkdir(parents=True, exist_ok=True)
        sprite.save(target)
        sprites[record["frame"]] = sprite
        geometry = record["original_geometry"]
        height_delta = extra * geometry["h"] / ch
        frame.update(geometry, h=geometry["h"] + height_delta,
                     y=geometry["y"] + height_delta / 2)

    # Keep all old compressed pixels intact. Four repaired sprites get their own page.
    with zipfile.ZipFile(ROOT / "anim/wili.zip") as source:
        runtime = codec.parse_build(source.read("build.bin"))
        changed = copy.deepcopy(runtime)
        if ATLAS not in changed["atlases"]:
            changed["atlases"].append(ATLAS)
        page = changed["atlases"].index(ATLAS)
        atlas = Image.new("RGBA", (2048, 512))
        x, y = 8, 8
        for symbol in changed["symbols"]:
            if symbol["name"] != "headbase":
                continue
            for frame in symbol["frames"]:
                sprite = sprites[frame["frame"]]
                if x + sprite.width + 8 > atlas.width or y + sprite.height + 8 > atlas.height:
                    raise ValueError("Repaired sprites no longer fit the head atlas")
                atlas.paste(sprite, (x, y))
                frame.update({k: frames[frame["frame"]][k] for k in ("x", "y", "w", "h")})
                left, top = frame["x"] - frame["w"] / 2, frame["y"] - frame["h"] / 2
                right, bottom = left + frame["w"], top + frame["h"]
                u0, u1 = x / atlas.width, (x + sprite.width) / atlas.width
                v0, v1 = 1 - y / atlas.height, 1 - (y + sprite.height) / atlas.height
                vertices = [(left, top, 0, u0, v0, page), (right, top, 0, u1, v0, page),
                            (left, bottom, 0, u0, v1, page), (right, top, 0, u1, v0, page),
                            (right, bottom, 0, u1, v1, page), (left, bottom, 0, u0, v1, page)]
                if frame["vertex_count"] != 6:
                    raise ValueError("Expected the existing rectangular sprite topology")
                start = frame["vertex_start"]
                changed["vertices"][start:start + 6] = vertices
                x += sprite.width + 16
        output.mkdir(parents=True, exist_ok=True)
        atlas_png = output / "head-atlas.png"
        atlas_tex = output / ATLAS
        atlas.save(atlas_png)
        encode_tex(atlas_png, atlas_tex)
        runtime_path = output / "anim/wili.zip"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(runtime_path, "w", zipfile.ZIP_DEFLATED) as dest:
            for info in source.infolist():
                if info.filename not in ("build.bin", ATLAS):
                    dest.writestr(info, source.read(info.filename))
            # Fixed timestamps make reruns reproducible.
            for name, contents in (("build.bin", serialize(changed)), (ATLAS, atlas_tex.read_bytes())):
                info = zipfile.ZipInfo(name, (2026, 10, 23, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                dest.writestr(info, contents)
    source_build["atlases"] = changed["atlases"]
    target_build = output / SOURCE / "build.json"
    target_build.write_text(json.dumps(source_build, indent=2) + "\n")
    print(json.dumps({"output": str(output), "restored_frames": sorted(sprites),
                      "runtime_sha256": hashlib.sha256(runtime_path.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "art/.work/head-tip-fix")
    args = parser.parse_args()
    output = args.out.resolve()
    if output == ROOT:
        raise ValueError("Choose a separate review directory")
    restore(output)
