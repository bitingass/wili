"""Portable PNG -> OpenGL KTEX BC3 encoder (Pillow with DDS/DXT5 support).

Usage:
    python art/tools/encode_ktex.py --input atlas.png --out atlas.tex
    python art/tools/encode_ktex.py --self-test

``encode_tex(png, output, texture_format="bc3")`` has the existing pipeline's
signature; importing this module does not change that pipeline. Compression is
lossy and is NOT byte-identical to Klei's Squish/FreeImage implementation.

Format evidence:
* Current runtime KTEX files use the post-caves 4/5/4/5/2-bit header layout,
  all-one flag/reserved bits, OpenGL=0, BC3=2, and 2D=1. For example the 12-level
  2048x2048 character atlas has flags 0xfffd8220 and first pitch 8192.
* Klei's original source confirms BC3=Dxt5, ceil(width/4)*16 pitch, vertical
  flipping for OpenGL, round(rgb*alpha/255), and halving mip dimensions to 1.
  https://github.com/kleientertainment/ds_mod_tools/blob/master/src/lib/texturelib/converters/PixelFormatConverter.cpp
  https://github.com/kleientertainment/ds_mod_tools/blob/master/src/lib/texturelib/converters/TextureOpenGL.cpp
  https://github.com/kleientertainment/ds_mod_tools/blob/master/src/lib/texturelib/InputImage.cpp
  https://github.com/kleientertainment/ds_mod_tools/blob/master/src/app/textureconverter/main.cpp
  Its public repository omits renderlib/BaseTexture.h, so the full header layout
  is checked against this project's existing files/decoder rather than claimed
  to be present in that public source.

Like Klei's converter, each mip is resized from the original straight-alpha
image, then premultiplied and flipped. Channels are resized independently to
avoid Pillow silently premultiplying RGBA during resize. Pillow's Lanczos and
BC3 encoder can differ from FreeImage/Squish; the container layout is identical.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import struct
import tempfile

from PIL import Image


HEADER = struct.Struct("<4sI")
MIP_HEADER = struct.Struct("<HHHI")
MIP_COUNT_MASK = 31 << 13
# Preserve the two flags and twelve reserved bits found in current game assets.
BASE_FLAGS = 0xFFFC0000 | (2 << 4) | (1 << 9)


def mip_sizes(width: int, height: int):
    """Yield the complete mip chain, including levels smaller than a BC3 block."""
    if not (1 <= width <= 65535 and 1 <= height <= 65535):
        raise ValueError("KTEX width and height must fit nonzero uint16 fields")
    if ((width + 3) // 4) * 16 > 65535:
        raise ValueError("BC3 row pitch exceeds KTEX's uint16 field")
    while True:
        yield width, height
        if (width, height) == (1, 1):
            break
        width, height = max(1, width // 2), max(1, height // 2)


def tex_info(data: bytes) -> dict:
    """Strictly validate this encoder's KTEX layout, including all mip payloads."""
    if len(data) < HEADER.size:
        raise ValueError("Truncated KTEX header")
    magic, flags = HEADER.unpack_from(data)
    if magic != b"KTEX" or flags & ~MIP_COUNT_MASK != BASE_FLAGS:
        raise ValueError("Expected current OpenGL/2D/BC3 KTEX header")
    count = (flags >> 13) & 31
    offset = HEADER.size + count * MIP_HEADER.size
    if not count or len(data) < offset:
        raise ValueError("Missing or truncated mip descriptors")
    mips = [MIP_HEADER.unpack_from(data, HEADER.size + i * MIP_HEADER.size)
            for i in range(count)]
    expected_sizes = list(mip_sizes(*mips[0][:2]))
    if [m[:2] for m in mips] != expected_sizes:
        raise ValueError("Expected a complete, ordered mip chain through 1x1")
    for width, height, pitch, size in mips:
        expected_pitch = ((width + 3) // 4) * 16
        if pitch != expected_pitch or size != pitch * ((height + 3) // 4):
            raise ValueError("Incorrect BC3 mip pitch or payload size")
    if offset + sum(m[3] for m in mips) != len(data):
        raise ValueError("KTEX payload is truncated or has trailing bytes")
    return {"flags": flags, "compression": 2, "mips": mips}


def _bc3_payload(image: Image.Image) -> bytes:
    buffer = BytesIO()
    try:
        image.save(buffer, format="DDS", pixel_format="DXT5")
    except (OSError, ValueError) as error:
        raise RuntimeError("Pillow with DDS/DXT5 encoding support is required") from error
    dds = buffer.getvalue()
    # DXT5 uses the classic 128-byte DDS header, without a DX10 extension.
    if (len(dds) < 128 or dds[:4] != b"DDS "
            or struct.unpack_from("<I", dds, 4)[0] != 124
            or dds[84:88] != b"DXT5"):
        raise RuntimeError("Pillow did not produce a classic DXT5 DDS")
    height, width = struct.unpack_from("<II", dds, 12)
    expected_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if (width, height) != image.size or len(dds) != 128 + expected_size:
        raise RuntimeError("Unexpected DXT5 dimensions or block payload length")
    return dds[128:]


def encode_image(image: Image.Image) -> bytes:
    """Encode straight-alpha artwork; never resize the base level or edit the input."""
    sizes = list(mip_sizes(*image.size))
    original = image.convert("RGBA")
    channels = original.split()
    descriptors, payloads = [], []
    for size in sizes:
        mip = original if size == original.size else Image.merge(
            "RGBA", [channel.resize(size, Image.Resampling.LANCZOS) for channel in channels])
        # RGBa's lowercase a means premultiplied alpha. Reinterpret these bytes
        # as RGBA for the DDS compressor; converting back would unpremultiply.
        premultiplied = Image.frombytes("RGBA", size, mip.convert("RGBa").tobytes())
        payload = _bc3_payload(premultiplied.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
        pitch = ((size[0] + 3) // 4) * 16
        descriptors.append(MIP_HEADER.pack(*size, pitch, len(payload)))
        payloads.append(payload)
    data = (HEADER.pack(b"KTEX", BASE_FLAGS | (len(sizes) << 13))
            + b"".join(descriptors) + b"".join(payloads))
    tex_info(data)
    return data


def encode_tex(png, output, texture_format="bc3"):
    """Drop-in explicit callable for the pipeline's BC3 conversion step."""
    if texture_format.lower() not in ("bc3", "dxt5"):
        raise ValueError("This portable encoder supports only BC3/DXT5")
    source, destination = Path(png), Path(output)
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output must be different files")
    with Image.open(source) as image:
        data = encode_image(image)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return tex_info(data)


def decode_mip(data: bytes, level: int = 0, *, unpremultiply: bool = True):
    """Decode one mip with Pillow, returning top-down pixels for inspection."""
    info = tex_info(data)
    mips = info["mips"]
    if not 0 <= level < len(mips):
        raise ValueError("Mip level is outside the chain")
    width, height, _, size = mips[level]
    offset = HEADER.size + MIP_HEADER.size * len(mips) + sum(m[3] for m in mips[:level])
    image = Image.frombytes("RGBA", (width, height), data[offset:offset + size], "bcn", (3,))
    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if unpremultiply:
        image = Image.frombytes("RGBa", image.size, image.tobytes()).convert("RGBA")
    return image


def self_test() -> dict:
    """Exercise header, transparency, orientation, small/NPOT mips and file I/O."""
    image = Image.new("RGBA", (16, 16))
    swatches = [(255, 0, 0, 255), (0, 255, 0, 128),
                (0, 0, 255, 0), (255, 255, 0, 255)]
    for color, box in zip(swatches, [(0, 0, 8, 8), (8, 0, 16, 8),
                                      (0, 8, 8, 16), (8, 8, 16, 16)]):
        image.paste(color, box)
    data = encode_image(image)
    info = tex_info(data)
    # Literal expected header, independent of the writer's shifts/constants.
    assert data[:8] == bytes.fromhex("4b54455820a2fcff")
    assert info["mips"] == [(16, 16, 64, 256), (8, 8, 32, 64),
                            (4, 4, 16, 16), (2, 2, 16, 16), (1, 1, 16, 16)]
    raw = decode_mip(data, unpremultiply=False)
    expected = [(255, 0, 0, 255), (0, 128, 0, 128),
                (0, 0, 0, 0), (255, 255, 0, 255)]
    for xy, color in zip([(2, 2), (10, 2), (2, 10), (10, 10)], expected):
        assert max(abs(a - b) for a, b in zip(raw.getpixel(xy), color)) <= 4
    restored = decode_mip(data)
    assert restored.getpixel((10, 2))[1] >= 250  # no double premultiplication
    assert encode_image(image) == data
    tested_sizes = [(1, 1), (2, 2), (3, 5), (7, 9), (1, 16), (16, 1), (32, 8)]
    for size in tested_sizes:
        candidate = encode_image(Image.new("RGBA", size, (64, 128, 192, 128)))
        mip_info = tex_info(candidate)["mips"]
        for index, mip in enumerate(mip_info):
            assert decode_mip(candidate, index).size == mip[:2]
        assert mip_info[-1] == (1, 1, 16, 16)
    for invalid in [data[:7], data[:-1], data + b"\0"]:
        try:
            tex_info(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed KTEX was accepted")
    with tempfile.TemporaryDirectory(prefix="wili_ktex_test_") as temp:
        source, output = Path(temp) / "input.png", Path(temp) / "output.tex"
        image.save(source)
        assert encode_tex(source, output) == info
        assert output.read_bytes() == data
    return {"passed": True, "swatch_size": image.size, "mips": len(info["mips"]),
            "additional_sizes": tested_sizes, "checked": ["header", "pitch", "mip chain",
            "BC3 decode", "vertical orientation", "premultiplied alpha", "determinism",
            "truncated input rejection", "file round trip"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--format", choices=["bc3", "dxt5"], default="bc3")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        if args.input or args.out:
            parser.error("Use --self-test separately from --input/--out")
        result = self_test()
    else:
        if args.input is None or args.out is None:
            parser.error("Both --input and --out are required")
        result = encode_tex(args.input, args.out, args.format)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
