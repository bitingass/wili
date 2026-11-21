"""Build Wili's two reverse-grip attack clips from the installed game animation.

Usage: python art/tools/build_wili_scimitar_attack.py --source PATH_TO/player_attacks.zip
The default output is in art/.work for review before installing in anim/.
"""
import argparse
import copy
from pathlib import Path
import struct
from zipfile import ZipFile, ZIP_DEFLATED

from render_workshop_native import parse_anim

# Inclusive 0-based frame ranges. The wind-up and swing are six and nineteen
# frames long, respectively. Keep the idle transitions in their native order.
FRONT_HAND_RANGES = {
    ("atk_pre", 5): (2, 5),
    ("atk", 5): (0, 9),
    ("atk", 8): (2, 9),
    ("atk", 2): (2, 9),
}
ARM_TIP_SYMBOLS = {"hand", "arm_lower", "arm_lower_cuff", "swap_object"}
BODY_SYMBOLS = {"face", "hairfront", "headbase", "headbase_hat", "hair",
                "hairpigtails", "torso", "torso_pelvis"}


def draw_carry_arm_in_front(frame, names):
    # DST stores foreground first. Move the wrist with its weapon so that the
    # fingers still wrap around the grip. Use existing depth slots, leaving
    # every screen-space matrix and every other pair's draw order intact.
    old = sorted(frame["elements"], key=lambda element: element["matrix"][6])
    wrist = [e for e in old if names[e["layer"]] == "ARM_carry" and names[e["symbol"]] in ARM_TIP_SYMBOLS]
    if not any(names[e["symbol"]] == "swap_object" for e in wrist):
        raise ValueError("Attack clip has no equipped weapon on the expected arm")
    outside = [e for e in old if e not in wrist]
    index = next(i for i, e in enumerate(outside) if names[e["symbol"]] in BODY_SYMBOLS)
    depths = [e["matrix"][6] for e in old]
    ordered = outside[:index] + wrist + outside[index:]
    for element, depth in zip(ordered, depths):
        element["matrix"][6] = depth
    frame["elements"] = ordered


def make_clips(native):
    result = []
    for anim in native["anims"]:
        if anim["name"] not in ("atk_pre", "atk"):
            continue
        clip = copy.deepcopy(anim)
        clip["name"] = "wili_scimitar_" + anim["name"]
        limits = FRONT_HAND_RANGES.get((anim["name"], anim["facing"]))
        if limits is not None:
            start, end = limits
            for frame in clip["frames"][start:end + 1]:
                draw_carry_arm_in_front(frame, native["names"])
        result.append(clip)
    if {(a["name"], a["facing"]) for a in result} != {
        (name, facing) for name in ("wili_scimitar_atk_pre", "wili_scimitar_atk") for facing in (2, 5, 8)
    }:
        raise ValueError("Unexpected attack animation names or directions")
    return result


def serialize(animations, names):
    data = bytearray()
    def put(fmt, *values):
        data.extend(struct.pack("<" + fmt, *values))
    def string(value):
        encoded = value.encode("utf-8")
        put("I", len(encoded))
        data.extend(encoded)
    frames = [f for a in animations for f in a["frames"]]
    put("4s5I", b"ANIM", 4, sum(len(f["elements"]) for f in frames), len(frames),
        sum(len(f["events"]) for f in frames), len(animations))
    for a in animations:
        string(a["name"])
        put("BIfI", a["facing"], a["root"], a["fps"], len(a["frames"]))
        for f in a["frames"]:
            put("4fI", *f["bbox"], len(f["events"]))
            for event in f["events"]:
                put("I", event)
            put("I", len(f["elements"]))
            for e in f["elements"]:
                put("3I7f", e["symbol"], e["frame"], e["layer"], *e["matrix"])
    put("I", len(names))
    for key, value in names.items():
        put("I", key)
        string(value)
    return bytes(data)


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=root / "art/.work/wili_scimitar_attack.zip")
    args = parser.parse_args()
    if args.out.resolve() == args.source.resolve():
        parser.error("Choose an output separate from the original game archive")
    with ZipFile(args.source) as src:
        original = src.read("anim.bin")
    native = parse_anim(original)
    if serialize(native["anims"], native["names"]) != original:
        raise ValueError("Unsupported source animation format")
    payload = serialize(make_clips(native), native["names"])
    parse_anim(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.out, "w", ZIP_DEFLATED) as packed:
        packed.writestr("anim.bin", payload)


if __name__ == "__main__":
    main()
