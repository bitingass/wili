"""Build the registered Eclipse Shiv sprites and its eight natural moon loops."""
from functools import lru_cache
from pathlib import Path
import argparse
import json
import math
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import numpy as np
from PIL import Image

import dst_art_pipeline as codec
from build_wili_scimitar_attack import serialize
from anim_draw_order import normalize_draw_order
from encode_ktex import encode_image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "art/source"
DESIGN = SOURCE / "illustrations/weapon/eclipse-shiv"
sys.path.insert(0, str(DESIGN))
import eclipse_looks

BANK = "wili_eclipse_shiv"
WORK = ROOT / "art/.work/envoy-model/weapon"
CANVAS = (320, 330)
PIVOT = np.array([138., 83.])
EDGE_RESOLUTION = 2
HELD_SCALE = 1.20
GROUND_SCALE = 1.15
OUTLINE_RADIUS = 2.15
OUTLINE_TAPER_MIN = 0.62
OUTLINE_INK_RGB = (6, 7, 10)
POST_INK_LOCK = 0.55
R = Image.Resampling
PLACEMENT = json.loads((DESIGN.parent / "placement.json").read_text(encoding="utf8"))
REGISTER = json.loads((DESIGN / "registration.json").read_text(encoding="utf8"))
SOURCE_GRIP = np.array(REGISTER["grip"], dtype=float)
SOURCE_TIP = np.array(REGISTER["tip"], dtype=float)
SWAP = json.loads((SOURCE / "anim/swap_scimitar/build.json").read_text(encoding="utf8"))
PROP = json.loads((SOURCE / "anim/scimitar/build.json").read_text(encoding="utf8"))


def axes(v):
    x, y = v / np.linalg.norm(v)
    return np.array(((x, -y), (y, x)))


# Use the original grip and direction; size the blade by the palm-to-tip
# fraction in the blueprint's held-weapon inset (the pommel is occluded).
old = PLACEMENT["held"][0]
held_size = json.loads((DESIGN / "design.json").read_text(encoding="utf8"))["held_size"]
reference_span = np.linalg.norm(np.subtract(held_size["reference_tip_px"],held_size["reference_palm_px"]))
target_reach = reference_span / held_size["reference_figure_height_px"] * held_size["game_front_idle_height_units"]
held_scale = target_reach / held_size["prior_projected_palm_to_tip_units"]
REACH = (np.array(PLACEMENT["source_tip"]) - old["source_grip_anchor"]) * old["pixel_scale"] * held_scale
MATRIX = (axes(REACH) @ np.diag((1., -1.)) @ axes(SOURCE_TIP-SOURCE_GRIP).T
          * (np.linalg.norm(REACH) / np.linalg.norm(SOURCE_TIP-SOURCE_GRIP)))


def project(art, dest=PIVOT, size=CANVAS, scale=1.):
    inverse = np.linalg.inv(MATRIX * scale)
    shift = SOURCE_GRIP - inverse @ dest
    # Prefilter before rotating fine ink and source paper onto game texels.
    pre = .5
    reduced = art.resize((art.width//2, art.height//2), R.LANCZOS)
    m = pre * inverse
    p = pre * shift
    return reduced.transform(tuple(size), Image.Transform.AFFINE,
                             (*m[0], p[0], *m[1], p[1]), R.BICUBIC)


def apply_shiv_ink(sprite, radius_px, taper_min=OUTLINE_TAPER_MIN, ink_rgb=OUTLINE_INK_RGB, ink_lock=POST_INK_LOCK):
    """Apply crisp DST jet-black outer contour and lock resampled interior ink."""
    if ink_lock > 0:
        arr = np.asarray(sprite, dtype=np.float32).copy()
        a = arr[:, :, 3] / 255.0
        rgb = arr[:, :, :3]
        lum = rgb @ np.array((0.253, 0.60, 0.147), dtype=np.float32)
        dark = np.clip((34.0 - lum) / 20.0, 0.0, 1.0) * np.clip((a - 0.4) / 0.4, 0.0, 1.0) * ink_lock
        ink_arr = np.array(ink_rgb, dtype=np.float32)
        arr[:, :, :3] = rgb * (1.0 - dark[..., None]) + ink_arr * dark[..., None]
        sprite = Image.fromarray(np.rint(np.clip(arr, 0, 255)).astype(np.uint8), "RGBA")
    alpha = np.asarray(sprite.getchannel("A"), dtype=np.float32) / 255.0
    solid = alpha > 0.5
    left = np.argmax(solid, axis=1)
    right = alpha.shape[1] - np.argmax(solid[:, ::-1], axis=1)
    width = np.where(solid.any(axis=1), right - left, 0)
    row_radius = radius_px * (taper_min + (1.0 - taper_min) * np.clip(width / 17.0, 0.0, 1.0))
    extent = math.ceil(radius_px + 0.5)
    height, cols = alpha.shape
    padded = np.pad(alpha, extent)
    expanded = alpha.copy()
    for dy in range(-extent, extent + 1):
        for dx in range(-extent, extent + 1):
            distance = math.hypot(dx, dy)
            if distance >= radius_px + 0.5:
                continue
            nearby = padded[extent + dy:extent + dy + height, extent + dx:extent + dx + cols]
            coverage = np.clip(row_radius + 0.5 - distance, 0, 1)
            np.maximum(expanded, nearby * coverage[:, None], out=expanded)
    underlay = Image.new("RGBA", sprite.size, (*ink_rgb, 0))
    underlay.putalpha(Image.fromarray(np.rint(expanded * 255).astype(np.uint8)))
    underlay.alpha_composite(sprite)
    return underlay


@lru_cache(maxsize=1)
def ground_layout():
    art = project(eclipse_looks.master())
    solid = np.asarray(art.getchannel("A")) > 127
    rows = np.where(solid)[0]
    binding = PLACEMENT["ground"]
    scale = GROUND_SCALE * binding["full_pixel_height_target"] / (rows.max() - rows.min() + 1)
    floor = binding["ground_line_png"]
    gy = binding["target_tip_png"][1] - REACH[1]*scale
    cut = round(PIVOT[1] + (floor-gy)/scale)
    xs = np.flatnonzero(solid[cut-1])
    if not len(xs):
        raise ValueError("The planted knife does not cross the soil plane.")
    gx = binding["contact_center_png"][0] - ((xs[0]+xs[-1])/2 - PIVOT[0])*scale
    # Match the native soil line exactly at the clipped atlas row.
    gy = floor - (cut-PIVOT[1])*scale
    return scale, np.array((gx,gy)), cut


def editable_sprites():
    art = eclipse_looks.surface("waxing_half")
    for idx, slot in enumerate(PLACEMENT["held"]):
        path = SOURCE/"anim/swap_scimitar/sprites"/slot["file"]
        sprite = project(art, np.array(slot["target_grip_anchor_png"]), slot["canvas_size"], HELD_SCALE)
        bounds = sprite.getchannel("A").point(lambda n:255 if n>40 else 0).getbbox()
        if min(bounds[0], bounds[1]) <= 0 or bounds[2]>=sprite.width or bounds[3]>=sprite.height:
            raise ValueError(f"Held frame {idx} clipped: {bounds}")
        sprite.save(path)
    binding = PLACEMENT["ground"]
    scale, anchor, _ = ground_layout()
    ground = project(art, anchor, binding["canvas_size"], scale)
    floor = round(binding["ground_line_png"])
    ground.paste((0,0,0,0),(0,floor,ground.width,ground.height))
    ground.save(SOURCE/"anim/scimitar/sprites"/binding["file"])
    icon = art.crop(art.getbbox())
    icon.thumbnail((56,56),R.LANCZOS)
    inventory = Image.new("RGBA",(64,64))
    inventory.paste(icon,((64-icon.width)//2,(64-icon.height)//2))
    inventory = apply_shiv_ink(inventory, radius_px=1.25, taper_min=0.70, ink_lock=0.45)
    inventory.save(SOURCE/"ui/images/inventoryimages/scimitar.png")


def world_at(slot, canvas, location):
    unit = np.array((slot["w"],slot["h"]))/canvas
    center = np.array((slot["x"],slot["y"]))
    return center+(location-np.array(canvas)/2)*unit, unit


def light_overlay(surface, lit):
    """Extract only changing light/particles from two registered straight-alpha cels."""
    # In premultiplied colour, target = layer + surface * (1 - layer_alpha).
    # On opaque metal the colour channels give the smallest possible layer
    # alpha. Unchanged ink therefore stays entirely on the physical weapon.
    base = np.asarray(surface).astype(np.float32)/255
    target = np.asarray(lit).astype(np.float32)/255
    base[:,:,:3] *= base[:,:,3:4]
    target[:,:,:3] *= target[:,:,3:4]
    delta = target - base
    cover = np.where(delta >= 0, delta/np.maximum(1-base, 1e-6),
                     -delta/np.maximum(base, 1e-6))
    alpha = np.clip(cover.max(axis=2,keepdims=True), 0, 1)
    rgb = base[:,:,:3] + delta[:,:,:3]/np.maximum(alpha, 1e-6)
    rgba = np.concatenate((np.clip(rgb,0,1),alpha), axis=2)
    return Image.fromarray(np.rint(rgba*255).astype(np.uint8))


def build_assets():
    norm_size = np.array(PLACEMENT["held"][0]["canvas_size"])
    hand_origins = []
    for i, slot in enumerate(SWAP["symbols"][0]["frames"]):
        grip = np.array(PLACEMENT["held"][i]["target_grip_anchor_png"])
        origin, held_unit = world_at(slot,norm_size,grip)
        hand_origins.append(origin)
    held_unit *= HELD_SCALE
    ground_record = PLACEMENT["ground"]
    ground_scale, ground_grip, cut = ground_layout()
    ground_origin, ground_unit = world_at(PROP["symbols"][0]["frames"][0],
                                          np.array(ground_record["canvas_size"]),ground_grip)
    ground_unit *= ground_scale
    symbols = []; clips = []; tiles = {}; alias = {}
    names = {codec.hash_name(BANK):BANK}

    def symbol(name,frames):
        key=codec.hash_name(name)
        names[key]=name
        symbols.append(dict(name=name,hash=key,frames=frames))
        return key

    def record(frame,duration,rect,origin,unit,png):
        l,t,r,b=rect
        center=origin+(np.array(((l+r)/2,(t+b)/2))-PIVOT)*unit
        return dict(frame=frame,duration=duration,x=center[0],y=center[1],
                    w=(r-l)*unit[0],h=(b-t)*unit[1],png=png)

    def element(key,frame,translation=(0,0),depth=-5):
        return dict(symbol=key,layer=key,frame=frame,matrix=[1,0,0,1,*translation,depth])

    def clip(name,timeline,boxes):
        # These coordinates are conservative, stable throughout a single loop.
        left=min(x-w/2 for x,y,w,h in boxes);right=max(x+w/2 for x,y,w,h in boxes)
        top=min(y-h/2 for x,y,w,h in boxes);bottom=max(y+h/2 for x,y,w,h in boxes)
        bbox=[(left+right)/2,(top+bottom)/2,right-left,bottom-top]
        frames = [normalize_draw_order(dict(bbox=bbox, events=[], elements=els))
                  for els in timeline]
        clips.append(dict(name=name,root=codec.hash_name(BANK),facing=255,fps=25,frames=frames))

    grass=PROP["symbols"][1]
    grass_frame=grass["frames"][0].copy();grass_frame["png"]="grass"
    tiles["grass"]=codec.read_sprite(SOURCE/"anim/scimitar/sprites",grass["frames"][0],grass)
    grass_key=symbol("shiv_ground_grass",[grass_frame])
    def bbox(fr,offset=(0,0)):
        return [fr["x"]+offset[0],fr["y"]+offset[1],fr["w"],fr["h"]]
    # Preserve the source GIF's 30 individual drawings. Smaller glints need
    # sub-unit texels at the game grip, but the frame bounds remain in the
    # original animation coordinates for hands, followers and ground contact.
    density=EDGE_RESOLUTION
    edge_canvas=tuple(v*density for v in CANVAS)
    def project_cel(image):
        return project(image, dest=PIVOT*density, size=edge_canvas, scale=density)

    def tile(name, image):
        rect = image.getchannel("A").getbbox()
        if rect is None:
            raise ValueError(f"Empty shiv tile: {name}")
        tiles[name] = image.crop(rect)
        return np.array(rect)

    def planted(name, frame, rect):
        l,t,r,b = rect
        bottom = min(b,cut*density)
        if bottom <= t:
            raise ValueError(f"No pixels above soil: {name}")
        alias[name+"_cut"] = (name,bottom-t)
        return record(frame,1,np.array((l,t,r,bottom))/density,
                      ground_origin,ground_unit,name+"_cut")

    count=eclipse_looks.FRAMES
    for phase in eclipse_looks.PHASES:
        surface = project_cel(eclipse_looks.surface(phase))
        weapon_name = "shiv_weapon_" + phase
        outlined = apply_shiv_ink(surface, OUTLINE_RADIUS*density)
        weapon_rect = tile(weapon_name, outlined)
        symbol(weapon_name, [record(idx,3,weapon_rect/density,origin,held_unit,weapon_name)
                             for idx,origin in zip((0,5),hand_origins)])
        ground_weapon = planted(weapon_name,0,weapon_rect)
        ground_weapon_key = symbol("shiv_planted_"+phase,[ground_weapon])
        held_frames=[];ground_frames=[]
        for i in range(count):
            key=f"{phase}_{i}"
            lit=project_cel(eclipse_looks.weapon(phase,time=i*eclipse_looks.PERIOD/count))
            rect=tile(key, light_overlay(surface,lit))
            held_frames.append(record(i,1,rect/density,np.zeros(2),held_unit,key))
            ground_frames.append(planted(key,i,rect))
        held=symbol("shiv_glint_"+phase,held_frames)
        ground_glint=symbol("shiv_ground_glint_"+phase,ground_frames)
        for group,offset in zip(("a","b"),hand_origins):
            clip("held_"+group+"_"+phase,
                 [[element(held,n,offset)] for n in range(count)],
                 [bbox(fr,offset) for fr in held_frames])
        prop_shift=(.45,.10); grass_shift=(0,-2.15)
        clip("ground_"+phase,
             [[element(grass_key,0,grass_shift,-6),element(ground_glint,n,prop_shift,-5.1),
               element(ground_weapon_key,0,prop_shift)] for n in range(count)],
             [bbox(fr,prop_shift) for fr in ground_frames]+[bbox(ground_weapon,prop_shift),bbox(grass_frame,grass_shift)])

    # The game's ordinary two-atlas shader maps every z>=.5 to sampler 1.
    # Use one atlas so neither normal nor bloom paths can sample another cel.
    side=4096;padding=4;placements={};pages=[[]];extents=[[0,0]]
    x=y=padding;row=0
    for name,im in sorted(tiles.items(),key=lambda t:(-t[1].height,-t[1].width,t[0])):
        if x+im.width+padding>side:x,y,row=padding,y+row+2*padding,0
        if y+im.height+padding>side:
            pages.append([]);extents.append([0,0]);x=y=padding;row=0
        pages[-1].append((name,x,y));ex=extents[-1]
        ex[0]=max(ex[0],x+im.width+padding);ex[1]=max(ex[1],y+im.height+padding)
        x+=4*math.ceil((im.width+2*padding)/4);row=max(row,4*math.ceil(im.height/4))
    if len(pages)!=1:
        raise ValueError("Eclipse Shiv must fit one atlas; additional pages can flicker in the game renderer")
    atlas_names=[];assets={}
    for idx,(items,extent) in enumerate(zip(pages,extents)):
        w,h=(1<<(s-1).bit_length() for s in extent)
        atlas=Image.new("RGBA",(w,h))
        for name,x,y in items:
            im=tiles[name];atlas.paste(im,(x,y))
            placements[name]=dict(x=x,y=y,w=im.width,h=im.height,aw=w,ah=h,page=idx)
        name=f"atlas-{idx}.tex";atlas_names.append(name);assets[name]=encode_image(atlas)
    for name,(original,height) in alias.items():
        placements[name]=dict(placements[original],h=height)
    symbols.sort(key=lambda s:s["hash"])
    assets["build.bin"]=codec.serialize_build(dict(name=BANK,symbols=symbols),atlas_names,placements)
    assets["anim.bin"]=serialize(clips,names)
    return assets


def build_archive(out):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(out,"w") as archive:
        for name,data in build_assets().items():
            info=ZipInfo(name,(1980,1,1,0,0,0));archive.writestr(info,data,compress_type=ZIP_DEFLATED)
    print(f"{out} ({out.stat().st_size:,} bytes)")


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out",type=Path,default=WORK/(BANK+".zip"))
    cli.add_argument("--update-sprites",action="store_true")
    args=cli.parse_args()
    if args.update_sprites:editable_sprites()
    build_archive(args.out)
