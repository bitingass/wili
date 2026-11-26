"""Offline rendering of shipped DST ANIM poses with the current Wili PNG build.

This produces promotional animation assets, not gameplay recordings.
No gameplay Lua or source archives are loaded.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[2]
GAME = Path(r"F:\steam\steamapps\common\Don't Starve Together\data\anim")
OUT = PROJECT / "art/.work/workshop/native"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("dst_pipeline", PROJECT / "art/tools/dst_art_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def parse_anim(data):
    p = 0
    def read(fmt):
        nonlocal p
        values = struct.unpack_from("<" + fmt, data, p)
        p += struct.calcsize("<" + fmt)
        return values[0] if len(values) == 1 else values
    def string():
        return read(str(read("I")) + "s").decode("utf-8")
    assert read("4s") == b"ANIM"
    version, total_elements, total_frames, total_events, count = read("5I")
    assert version == 4
    anims = []
    ec = fc = evc = 0
    for _ in range(count):
        anim = dict(name=string(), facing=read("B"), root=read("I"), fps=read("f"), frames=[])
        for _ in range(read("I")):
            fr = dict(bbox=list(read("4f")), events=[read("I") for _ in range(read("I"))], elements=[])
            evc += len(fr["events"])
            for _ in range(read("I")):
                symbol, frame, layer = read("3I")
                fr["elements"].append(dict(symbol=symbol, frame=frame, layer=layer, matrix=list(read("7f"))))
                ec += 1
            anim["frames"].append(fr)
            fc += 1
        anims.append(anim)
    names = {read("I"): string() for _ in range(read("I"))}
    assert p == len(data), (p, len(data))
    assert (ec, fc, evc) == (total_elements, total_frames, total_events)
    return dict(anims=anims, names=names, header=dict(elements=ec, frames=fc, events=evc, animations=count))


def anim_archive(name, folder=GAME):
    path = folder / name
    with zipfile.ZipFile(path) as z:
        parsed = parse_anim(z.read("anim.bin"))
    parsed["source"] = str(path)
    parsed["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return parsed


def source_build(name):
    root = PROJECT / "art/source/anim" / name
    build = json.loads((root / "build.json").read_text(encoding="utf-8"))
    for symbol in build["symbols"]:
        for fr in symbol["frames"]:
            fr["image"] = pipeline.read_sprite(root / "sprites", fr, symbol)
    return build


def native_build(name):
    with zipfile.ZipFile(GAME / name) as z:
        build = pipeline.parse_build(z.read("build.bin"))
        arrays = [np.array(pipeline.decode_tex(z.read(n))) for n in build["atlases"]]
        for symbol in build["symbols"]:
            for fr in symbol["frames"]:
                fr["image"] = pipeline.reconstruct_frame(build, fr, arrays)
    return build


def frame_lookup(build):
    return {sym["hash"]: sym["frames"] for sym in build["symbols"]}


def get_frame(table, symbol, index):
    matches = [f for f in table.get(symbol, []) if f["frame"] <= index < f["frame"] + f["duration"]]
    if not matches:
        return None
    return matches[-1]


def render_frame(frame, table, names, size=(900, 1100), origin=(450, 1010), scale=2.0,
                 hide_layers=(), hide_symbols=(), overrides=None):
    canvas = Image.new("RGBA", size)
    missing = []
    # ANIM stores foreground first. The game paints the encoded array back
    # to front; it does not repair an artistically stale order from matrix Z.
    for elem in reversed(frame["elements"]):
        symbol_name = names.get(elem["symbol"], str(elem["symbol"]))
        layer_name = names.get(elem["layer"], str(elem["layer"]))
        if layer_name in hide_layers or symbol_name in hide_symbols:
            continue
        fr = get_frame(table, elem["symbol"], elem["frame"])
        if overrides and symbol_name in overrides:
            override_table, override_symbol = overrides[symbol_name]
            fr = get_frame(override_table, override_symbol, elem["frame"])
        if fr is None:
            missing.append(dict(symbol=symbol_name, layer=layer_name, frame=elem["frame"]))
            continue
        im = fr["image"]
        a,b,c,d,tx,ty,z = elem["matrix"]
        left, top = fr["x"] - fr["w"] / 2, fr["y"] - fr["h"] / 2
        forward = np.array([[scale*a*fr["w"]/im.width, scale*c*fr["h"]/im.height,
                             origin[0]+scale*(a*left+c*top+tx)],
                            [scale*b*fr["w"]/im.width, scale*d*fr["h"]/im.height,
                             origin[1]+scale*(b*left+d*top+ty)],
                            [0,0,1]], dtype=float)
        corners = forward @ np.array([[0,im.width,0,im.width],[0,0,im.height,im.height],[1,1,1,1]])
        bounds = (max(0,int(np.floor(corners[0].min()))-2),max(0,int(np.floor(corners[1].min()))-2),
                  min(size[0],int(np.ceil(corners[0].max()))+2),min(size[1],int(np.ceil(corners[1].max()))+2))
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            continue
        local_forward = forward.copy()
        local_forward[0,2] -= bounds[0]
        local_forward[1,2] -= bounds[1]
        inverse = np.linalg.inv(local_forward)
        transformed = im.transform((bounds[2]-bounds[0],bounds[3]-bounds[1]), Image.Transform.AFFINE, inverse[:2].flatten(), Image.Resampling.BICUBIC)
        canvas.alpha_composite(transformed, bounds[:2])
    return canvas, missing


def inspect():
    info = {}
    for n in ["player_idles.zip", "player_attacks.zip", "hound_basic.zip", "gems.zip"]:
        a = anim_archive(n)
        info[n] = dict(animations=[dict(name=x["name"],facing=x["facing"],frames=len(x["frames"])) for x in a["anims"]],
                       names=a["names"], header=a["header"])
    (OUT / "animation-catalog.json").write_text(json.dumps(info,indent=2), encoding="utf-8")
    print(json.dumps({n:v["animations"] for n,v in info.items()},indent=2))


def make_outputs():
    report = dict(kind="offline native animation assembly, not gameplay footage", sources={}, sequences={})
    player_table = frame_lookup(source_build("wili"))
    weapon_table = frame_lookup(source_build("swap_scimitar"))
    overrides = {"swap_object": (weapon_table, pipeline.hash_name("swap_spear"))}
    player_actions = [
        ("idle", anim_archive("player_idles.zip"), ("idle_loop",)),
        ("attack", anim_archive("wili_scimitar_attack.zip", PROJECT / "anim"),
         ("wili_scimitar_atk_pre", "wili_scimitar_atk")),
    ]
    for _, parsed, _ in player_actions:
        source = parsed["source"]
        report["sources"][Path(source).name] = dict(path=source, sha256=parsed["sha256"], header=parsed["header"])
    def export_sequence(label, sequences, table, size, origin, scale, hidden=(), symbols_hidden=(), overrides=None):
        folder = OUT / label
        folder.mkdir(exist_ok=True)
        frames, missing, indices = [],[],[]
        for parsed, anim in sequences:
            for index, fr in enumerate(anim["frames"]):
                im, miss = render_frame(fr, table, parsed["names"],size,origin,scale,hidden,symbols_hidden,overrides)
                path = folder / f"{len(frames):03}.png"
                im.save(path)
                frames.append(im)
                missing.extend(miss)
                indices.append(dict(source_animation=anim["name"],source_frame=index,path=str(path.relative_to(OUT)),alpha_bbox=im.getbbox()))
        unique_missing = [dict(t) for t in sorted({tuple(sorted(x.items())) for x in missing})]
        report["sequences"][label] = dict(canvas=list(size),anchor=list(origin),scale=scale,fps=30,
                                          count=len(frames),frames=indices,unresolved=unique_missing)
        return frames
    player_frames={}
    for direction,facing in [("front",8),("side",1)]:
        for action, parsed, anim_names in player_actions:
            anims=[(parsed,next(a for a in parsed["anims"] if a["name"]==name and a["facing"] & facing)) for name in anim_names]
            absent={v for k,v in parsed["names"].items() if k not in player_table and v not in overrides}
            key=f"wili_{action}_{direction}"
            player_frames[key]=export_sequence(key,anims,player_table,(900,1100),(450,1010),2.0,
                                               ("ARM_normal","HEAD_HAT","HAIR_HAT","HAT"),absent,overrides)
    hound_table=frame_lookup(native_build("hound.zip"))
    hound_anims=anim_archive("hound_basic.zip")
    report["sources"]["hound_basic.zip"]=dict(path=hound_anims["source"],sha256=hound_anims["sha256"],header=hound_anims["header"])
    for action in ["idle","hit","atk"]:
        seq=next(a for a in hound_anims["anims"] if a["name"]==action and a["facing"]==5)
        export_sequence("hound_"+action,[(hound_anims,seq)],hound_table,(1700,1700),(750,1320),2.0)
    gems_table=frame_lookup(native_build("gems.zip"))
    gems_anims=anim_archive("gems.zip")
    report["sources"]["gems.zip"]=dict(path=gems_anims["source"],sha256=gems_anims["sha256"],header=gems_anims["header"])
    for gem in ["redgem","orangegem","yellowgem","greengem","bluegem","purplegem","opalgem"]:
        seq=next(a for a in gems_anims["anims"] if a["name"]==gem+"_idle")
        images=export_sequence(gem,[(gems_anims,dict(seq,frames=seq["frames"][:1]))],gems_table,(600,600),(300,400),2.0)
        im=images[0]
        cropped=im.crop(im.getbbox())
        cropped.save(OUT/(gem+".png"))
        report["sequences"][gem]["cropped_png"]=gem+".png"
    for label in ["wili","swap_scimitar"]:
        runtime=PROJECT/"anim"/(label+".zip")
        report["sources"][label+".zip"]=dict(path=str(runtime),sha256=hashlib.sha256(runtime.read_bytes()).hexdigest())
    report["sources"]["hound.zip"]=dict(path=str(GAME/"hound.zip"),sha256=hashlib.sha256((GAME/"hound.zip").read_bytes()).hexdigest())
    (OUT/"manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    # A fixed-scale contact sheet, assembled only from renderer outputs.
    labels=[("idle front",player_frames["wili_idle_front"][0]),("idle side",player_frames["wili_idle_side"][0])]
    labels += [(f"attack side {i}",player_frames["wili_attack_side"][i]) for i in [0,5,8,11,15,20]]
    sheet=Image.new("RGB",(1600,1200),(180,185,195))
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf",22)
    for i,(label,im) in enumerate(labels):
        thumb=im.resize((450,550),Image.Resampling.LANCZOS)
        x=(i%4)*400-25;y=(i//4)*600+30
        sheet.paste(thumb,(x,y),thumb)
        draw.text(((i%4)*400+20,(i//4)*600+12),label,font=font,fill=(12,16,23))
    sheet.save(OUT/"character-review.png")
    print(json.dumps({k:{"count":v["count"],"unresolved":v["unresolved"]} for k,v in report["sequences"].items()},indent=2))


if __name__ == "__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    make_outputs()
