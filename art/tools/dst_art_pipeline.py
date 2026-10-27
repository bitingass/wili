"""DST v6 build/KTEX conversion and production packaging.

Format fields follow the installed Klei Mod Tools buildanimation.py. This tool
does not draw artwork. Export reconstructs every triangle, including disconnected
UV islands, into the original frame coordinate system. Pack accepts finished
transparent PNG artwork and preserves animation hashes, frame IDs and pivots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "art/.work"
MODTOOLS = Path(r"F:\steam\steamapps\common\Don't Starve Mod Tools\mod_tools")
CONVERTER = MODTOOLS / "tools/bin/TextureConverter.exe"


def hash_name(value):
    result = 0
    for ch in value.lower():
        result = (ord(ch) + (result << 6) + (result << 16) - result) & 0xffffffff
    return result


def known_symbols():
    source = Path(__file__).with_name("symbol-names.json")
    return {int(key): value for key, value in json.loads(source.read_text(encoding="utf-8")).items()}


def parse_build(data):
    offset = 0

    def read(fmt):
        nonlocal offset
        values = struct.unpack_from("<" + fmt, data, offset)
        offset += struct.calcsize("<" + fmt)
        return values[0] if len(values) == 1 else values

    def read_string():
        return read(str(read("I")) + "s").decode("utf-8")

    assert read("4s") == b"BILD"
    version, symbol_count, frame_count = read("III")
    assert version == 6, version
    build_name = read_string()
    atlases = [read_string() for _ in range(read("I"))]
    symbols = []
    for _ in range(symbol_count):
        symbol_hash, count = read("II")
        frames = []
        for _ in range(count):
            values = read("IIffffII")
            frames.append(dict(zip(("frame", "duration", "x", "y", "w", "h", "vertex_start", "vertex_count"), values)))
        symbols.append({"hash": symbol_hash, "frames": frames})
    vertices = [read("ffffff") for _ in range(read("I"))]
    stored_names = {}
    if offset < len(data):
        for _ in range(read("I")):
            key = read("I")
            stored_names[key] = read_string()
    assert offset == len(data), (offset, len(data))
    names = known_symbols() | stored_names
    for symbol in symbols:
        symbol["name"] = names.get(symbol["hash"], "hash_" + str(symbol["hash"]))
    assert sum(len(s["frames"]) for s in symbols) == frame_count
    return dict(name=build_name, version=version, symbol_count=symbol_count,
                frame_count=frame_count, atlases=atlases, symbols=symbols,
                vertices=vertices, stored_names=stored_names)


def tex_info(data):
    assert data[:4] == b"KTEX"
    flags = struct.unpack_from("<I", data, 4)[0]
    mip_count = (flags >> 13) & 31
    mips = [struct.unpack_from("<HHHI", data, 8 + 10 * i) for i in range(mip_count)]
    assert 8 + 10 * mip_count + sum(m[3] for m in mips) == len(data)
    return {"flags": flags, "compression": (flags >> 4) & 31, "mips": mips}


def decode_tex(data):
    info = tex_info(data)
    w, h, _, size = info["mips"][0]
    payload = data[8 + 10 * len(info["mips"]):][:size]
    compression = info["compression"]
    if compression in (0, 1, 2):
        im = Image.frombytes("RGBA", (w, h), payload, "bcn", ((1, 2, 3)[compression],))
    elif compression == 4:
        im = Image.frombytes("RGBA", (w, h), payload)
    elif compression == 5:
        im = Image.frombytes("RGB", (w, h), payload).convert("RGBA")
    else:
        raise ValueError("Unsupported KTEX compression " + str(compression))
    im = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    arr = np.array(im, dtype=np.float32)
    alpha = arr[:, :, 3:4]
    arr[:, :, :3] = np.where(alpha > 0, np.minimum(255, arr[:, :, :3] * 255 / np.maximum(alpha, 1)), 0)
    return Image.fromarray(np.rint(arr).astype(np.uint8), "RGBA")


def reconstruct_frame(build, frame, atlas_arrays):
    """Rasterize triangles at pixel centers, preserving islands and source pivot."""
    width, height = round(frame["w"]), round(frame["h"])
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    origin = np.array([frame["x"] - frame["w"] / 2, frame["y"] - frame["h"] / 2])
    verts = np.asarray(build["vertices"][frame["vertex_start"]:frame["vertex_start"] + frame["vertex_count"]], dtype=np.float64)
    assert len(verts) % 3 == 0
    for start in range(0, len(verts), 3):
        tri = verts[start:start + 3]
        points = tri[:, :2] - origin
        lo = np.maximum(0, np.floor(points.min(axis=0)).astype(int))
        hi = np.minimum([width, height], np.ceil(points.max(axis=0)).astype(int))
        if np.any(hi <= lo):
            continue
        xx, yy = np.meshgrid(np.arange(lo[0], hi[0]) + .5, np.arange(lo[1], hi[1]) + .5)
        ax, ay = points[0]
        bx, by = points[1]
        cx, cy = points[2]
        determinant = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(determinant) < 1e-8:
            continue
        a = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / determinant
        b = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / determinant
        c = 1 - a - b
        mask = (a >= -1e-7) & (b >= -1e-7) & (c >= -1e-7)
        atlas_id = round(tri[0, 5])
        assert np.allclose(tri[:, 5], atlas_id)
        atlas = atlas_arrays[atlas_id]
        ah, aw = atlas.shape[:2]
        u = a * tri[0, 3] + b * tri[1, 3] + c * tri[2, 3]
        v = a * tri[0, 4] + b * tri[1, 4] + c * tri[2, 4]
        sx = np.clip(np.floor(u * aw).astype(int), 0, aw - 1)
        sy = np.clip(np.floor((1 - v) * ah).astype(int), 0, ah - 1)
        dest = canvas[lo[1]:hi[1], lo[0]:hi[0]]
        dest[mask] = atlas[sy[mask], sx[mask]]
    return Image.fromarray(canvas, "RGBA")


def font(size):
    return ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", size)


def contact_sheet(symbol, sprites, output):
    frames = symbol["frames"]
    cols = min(5, len(frames))
    rows = math.ceil(len(frames) / cols)
    maxw = max(round(f["w"]) for f in frames)
    maxh = max(round(f["h"]) for f in frames)
    scale = min(3, max(1, 230 // max(maxw, maxh)))
    cellw, cellh = max(230, maxw * scale + 24), max(250, maxh * scale + 64)
    sheet = Image.new("RGB", (cols * cellw, rows * cellh + 55), "#c4c8ce")
    draw = ImageDraw.Draw(sheet)
    draw.text((16, 14), symbol["name"] + " / original frames", fill="#1b2231", font=font(23))
    layout = []
    for i, frame in enumerate(frames):
        left, top = (i % cols) * cellw, (i // cols) * cellh + 55
        filename = f'{symbol["name"]}-{frame["frame"]}.png'
        im = Image.open(sprites / filename).convert("RGBA")
        display = im.resize((im.width * scale, im.height * scale), Image.Resampling.NEAREST)
        x, y = left + (cellw - display.width) // 2, top + 38 + (cellh - 50 - display.height) // 2
        draw.rectangle((left + 2, top + 2, left + cellw - 3, top + cellh - 3), outline="#858f9c", width=1)
        draw.text((left + 10, top + 9), f'{frame["frame"]:02d}  {im.width}x{im.height}', fill="#1b2231", font=font(18))
        sheet.paste(display, (x, y), display)
        layout.append({"filename": filename, "frame": frame["frame"], "cell": [left, top, cellw, cellh], "display": [x, y, display.width, display.height], "native_size": list(im.size), "scale": scale})
    sheet.save(output)
    output.with_suffix(".layout.json").write_text(json.dumps(layout, indent=2), encoding="utf-8")


def export_archive(source, target):
    target.mkdir(parents=True, exist_ok=True)
    sprites = target / "sprites"
    sheets = target / "sheets"
    sprites.mkdir(exist_ok=True)
    sheets.mkdir(exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        build = parse_build(archive.read("build.bin"))
        build["source_zip"] = str(source.resolve())
        build["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        atlases = [decode_tex(archive.read(name)) for name in build["atlases"]]
        for i, atlas in enumerate(atlases):
            atlas.save(target / f"atlas-{i}.png")
        arrays = [np.array(im) for im in atlases]
        for symbol in build["symbols"]:
            for frame in symbol["frames"]:
                filename = f'{symbol["name"]}-{frame["frame"]}.png'
                reconstruct_frame(build, frame, arrays).save(sprites / filename)
                frame["png"] = filename
                frame["pivot_x"] = .5 - frame["x"] / frame["w"]
                frame["pivot_y"] = .5 + frame["y"] / frame["h"]
            contact_sheet(symbol, sprites, sheets / (symbol["name"] + ".png"))
    (target / "build.json").write_text(json.dumps(build, indent=2), encoding="utf-8")
    return {"name": build["name"], "symbols": build["symbol_count"], "frames": build["frame_count"], "sheets": [str(sheets / (s["name"] + ".png")) for s in build["symbols"]]}


def export_all():
    report = {"archives": [], "ui": []}
    for name in ("wili", "scimitar", "swap_scimitar", "ghost_wili_build"):
        report["archives"].append(export_archive(ROOT / "anim" / (name + ".zip"), WORK / "references" / name))
    files = [ROOT / "modicon.tex"] + sorted((ROOT / "images").rglob("*.tex")) + sorted((ROOT / "bigportraits").rglob("*.tex"))
    for source in files:
        relative = source.relative_to(ROOT)
        output = WORK / "references/ui" / relative.with_suffix(".png")
        output.parent.mkdir(parents=True, exist_ok=True)
        im = decode_tex(source.read_bytes())
        im.save(output)
        report["ui"].append({"source": str(relative), "size": list(im.size), "png": str(output)})
    (WORK / "references/manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def serialize_build(build, atlas_names, placements):
    data = bytearray()
    verts = []

    def write(fmt, *values):
        data.extend(struct.pack("<" + fmt, *values))

    def write_string(value):
        encoded = value.encode("utf-8")
        write("I", len(encoded))
        data.extend(encoded)

    write("4sIII", b"BILD", 6, len(build["symbols"]), sum(len(s["frames"]) for s in build["symbols"]))
    write_string(build["name"])
    write("I", len(atlas_names))
    for name in atlas_names:
        write_string(name)
    for symbol in build["symbols"]:
        write("II", symbol["hash"], len(symbol["frames"]))
        for frame in symbol["frames"]:
            p = placements[frame["png"]]
            # Artwork may be supplied at another resolution; its world-space
            # bbox and pivot are unchanged unless explicitly changed in JSON.
            left, top = frame["x"] - frame["w"] / 2, frame["y"] - frame["h"] / 2
            right, bottom = left + frame["w"], top + frame["h"]
            u0, u1 = p["x"] / p["aw"], (p["x"] + p["w"]) / p["aw"]
            v0, v1 = 1 - p["y"] / p["ah"], 1 - (p["y"] + p["h"]) / p["ah"]
            idx = len(verts)
            page = float(p["page"])
            verts.extend([(left, top, 0, u0, v0, page), (right, top, 0, u1, v0, page), (left, bottom, 0, u0, v1, page),
                          (right, top, 0, u1, v0, page), (right, bottom, 0, u1, v1, page), (left, bottom, 0, u0, v1, page)])
            write("IIffffII", frame["frame"], frame["duration"], frame["x"], frame["y"], frame["w"], frame["h"], idx, 6)
    write("I", len(verts))
    for vert in verts:
        write("ffffff", *vert)
    # A hash-name table is valid but optional in the original v6 format.
    names = {s["hash"]: s["name"] for s in build["symbols"] if not s["name"].startswith("hash_")}
    write("I", len(names))
    for key, name in names.items():
        write("I", key)
        write_string(name)
    return bytes(data)


def encode_tex(png, output, texture_format="bc3"):
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [str(CONVERTER), "-i", str(png), "-o", str(output), "-f", texture_format, "-p", "opengl", "--premultiply", "--mipmap"]
    completed = subprocess.run(args, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"TextureConverter failed ({completed.returncode}):\n{completed.stdout}\n{completed.stderr}")
    assert output.is_file(), output
    return tex_info(output.read_bytes())


def pack_archive(build_path, sprites, output, texture_format="bc3"):
    build = json.loads(build_path.read_text(encoding="utf-8"))
    animation_data = None
    if build.get("animation_file"):
        animation_data = (build_path.parent / build["animation_file"]).read_bytes()
        if animation_data[:4] != b"ANIM":
            raise ValueError("animation_file must contain a compiled ANIM resource")
    allframes = [f for s in build["symbols"] for f in s["frames"]]
    images = {f["png"]: Image.open(sprites / f["png"]).convert("RGBA") for f in allframes}
    padding = 4
    side = 2048
    for im in images.values():
        assert im.width + 2 * padding <= side and im.height + 2 * padding <= side
    ordered = sorted(images, key=lambda name: (-images[name].height, -images[name].width, name))
    page, x, y, rowh = 0, padding, padding, 0
    placements = {}
    extent = [[0, 0]]
    for name in ordered:
        im = images[name]
        if x + im.width + padding > side:
            x, y, rowh = padding, y + rowh + 2 * padding, 0
        if y + im.height + padding > side:
            page += 1
            extent.append([0, 0])
            x, y, rowh = padding, padding, 0
        placements[name] = {"page": page, "x": x, "y": y, "w": im.width, "h": im.height}
        extent[page][0] = max(extent[page][0], x + im.width + padding)
        extent[page][1] = max(extent[page][1], y + im.height + padding)
        x += im.width + 2 * padding
        rowh = max(rowh, im.height)
    sizes = [(2 ** math.ceil(math.log2(max(4, w))), 2 ** math.ceil(math.log2(max(4, h)))) for w, h in extent]
    atlases = [Image.new("RGBA", size) for size in sizes]
    for name, p in placements.items():
        p["aw"], p["ah"] = sizes[p["page"]]
        atlases[p["page"]].paste(images[name], (p["x"], p["y"]))
    atlas_names = [f"atlas-{i}.tex" for i in range(len(atlases))]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wili_atlas_") as tmp:
        temp = Path(tmp)
        for i, atlas in enumerate(atlases):
            png = temp / f"atlas-{i}.png"
            atlas.save(png)
            encode_tex(png, temp / atlas_names[i], texture_format)
        data = serialize_build(build, atlas_names, placements)
        check = parse_build(data)
        assert check["name"] == build["name"]
        assert check["frame_count"] == build["frame_count"]
        source_zip = Path(build["source_zip"])
        if not source_zip.is_absolute():
            source_zip = ROOT / source_zip
        if source_zip.resolve() == output.resolve():
            raise ValueError("Pack to a temporary ZIP before replacing the current runtime archive")
        with zipfile.ZipFile(source_zip) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as packed:
            for name in source.namelist():
                if name == "anim.bin" and animation_data is not None:
                    continue
                if name != "build.bin" and name not in build["atlases"]:
                    packed.writestr(name, source.read(name))
            if animation_data is not None:
                packed.writestr("anim.bin", animation_data)
            packed.writestr("build.bin", data)
            for name in atlas_names:
                packed.writestr(name, (temp / name).read_bytes())
    print(json.dumps({"output": str(output), "frames": build["frame_count"], "atlases": sizes, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export")
    unpack = sub.add_parser("unpack")
    unpack.add_argument("--input", type=Path, required=True)
    unpack.add_argument("--out", type=Path, required=True)
    encode = sub.add_parser("encode")
    encode.add_argument("--input", type=Path, required=True)
    encode.add_argument("--out", type=Path, required=True)
    encode.add_argument("--format", default="bc3")
    pack = sub.add_parser("pack")
    pack.add_argument("--build", type=Path, required=True)
    pack.add_argument("--sprites", type=Path, required=True)
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--format", default="bc3")
    args = parser.parse_args()
    if args.command == "export":
        export_all()
    elif args.command == "unpack":
        print(json.dumps(export_archive(args.input, args.out), indent=2))
    elif args.command == "encode":
        print(json.dumps(encode_tex(args.input, args.out, args.format), indent=2))
    else:
        pack_archive(args.build, args.sprites, args.out, args.format)


if __name__ == "__main__":
    main()
