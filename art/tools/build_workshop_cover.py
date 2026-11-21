"""Compose a promotional GIF using the mod's real animation frames.

This is an editorial animation, not a screen recording. The background and
portrait are image_gen artwork; characters, weapon and gems use native assets.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "art/workshop"
NATIVE = PROJECT / "art/.work/workshop/native"
SIZE = 1024
DURATION = 6.4
FPS = 12.5
TOTAL = 80
PAPER = (245, 238, 216, 255)
GOLD = (219, 193, 133, 255)
FROST = (153, 189, 224, 255)
MANIFEST = json.loads((NATIVE / "manifest.json").read_text(encoding="utf-8"))


def font(size, kind="cn"):
    names = {"cn": "msyhbd.ttc", "small": "msyh.ttc", "serif": "georgiab.ttf"}
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / names[kind]), size)


def text_at(draw, xy, text, size, fill=PAPER, kind="cn", spacing=0):
    f = font(size, kind)
    if not spacing:
        draw.text(xy, text, font=f, fill=fill, stroke_width=0)
        return
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=f, fill=fill)
        x += draw.textlength(char, font=f) + spacing


def text_center(draw, y, text, size, fill=PAPER, kind="cn"):
    f = font(size, kind)
    w = draw.textlength(text, font=f)
    draw.text(((SIZE-w)/2, y), text, font=f, fill=fill)


def base_art():
    im = Image.open(ROOT / "cover-backplate.png").convert("RGBA").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(im)
    text_at(d, (65, 72), "WILI", 136, kind="serif", spacing=1)
    text_at(d, (74, 238), "月影刺客", 59, spacing=6)
    text_at(d, (77, 326), "MOONSHADOW ASSASSIN", 17, FROST, "small", 1)
    d.line([(76, 374), (400, 374)], fill=(168, 188, 208, 130), width=2)
    text_at(d, (77, 396), "银月弯刀 · 瞬移突袭", 24, PAPER, "small")
    return im


@lru_cache(maxsize=1024)
def sprite_frame(name, frame_id, scale_milli, mirror=False, ghost=False):
    seq = MANIFEST["sequences"][name]
    item = seq["frames"][frame_id % len(seq["frames"])]
    raw = Image.open(NATIVE / item["path"]).convert("RGBA")
    bbox = raw.getbbox()
    # Crop empty padding but preserve the animation's common anchor.
    ax, ay = seq["anchor"]
    if mirror:
        raw = ImageOps.mirror(raw)
        ax = raw.width - ax
        bbox = raw.getbbox()
    scale = scale_milli / 1000
    ax = (ax-bbox[0])*scale
    ay = (ay-bbox[1])*scale
    raw = raw.crop(bbox)
    raw = raw.resize((max(1, round(raw.width*scale)), max(1, round(raw.height*scale))), Image.Resampling.LANCZOS)
    if ghost:
        tint = Image.new("RGBA", raw.size, (96, 148, 219, 0))
        tint.putalpha(raw.getchannel("A").point(lambda a: round(a*.45)))
        raw = tint
    return raw, (ax, ay)


def put_sprite(im, name, frame_id, pos, scale=.47, mirror=False, opacity=1., ghost=False):
    sprite, anchor = sprite_frame(name, frame_id, round(scale*1000), mirror, ghost)
    if opacity < 1:
        sprite = sprite.copy()
        sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a*max(0., opacity))))
    im.alpha_composite(sprite, (round(pos[0]-anchor[0]), round(pos[1]-anchor[1])))


def shadow(im, pos, width=120, opacity=110):
    layer = Image.new("RGBA", im.size)
    d = ImageDraw.Draw(layer)
    x,y = pos
    d.ellipse((x-width/2,y-7,x+width/2,y+10), fill=(6,10,19,opacity))
    im.alpha_composite(layer)


def interpolate(a,b,p):
    return (a[0]+(b[0]-a[0])*p, a[1]+(b[1]-a[1])*p)


START = (210, 853)
LEFT = (375, 853)
RIGHT = (695, 853)
WARPS = [(0.56, START, LEFT), (2.00, LEFT, RIGHT), (3.60, RIGHT, LEFT), (4.92, LEFT, START)]
ATTACKS = [(0.72, LEFT, 0), (2.16, RIGHT, 1), (3.76, LEFT, 0)]
HOUNDS = [(505, 850), (825, 860)]


def actor_state(t):
    pos = START
    for when, begin, end in WARPS:
        if t >= when + .16:
            pos = end
        elif t >= when:
            p = (t-when)/.16
            return "wili_idle_side", int(t*30), end if p > .5 else begin, abs(2*p-1)
    for when, attack_pos, target in ATTACKS:
        local = t-when
        if 0 <= local < 25/30:
            return "wili_attack_side", min(24,int(local*30)), attack_pos, 1.
    name = "wili_idle_front" if t >= 5.1 else "wili_idle_side"
    return name, int(t*30), pos, 1.


def warp_trails(im, t):
    for when, start, end in WARPS:
        local = t-when
        if 0 <= local <= .36:
            fade = 1-local/.36
            for k in range(3):
                p = (k+1)/4
                pos = interpolate(start, end, p)
                put_sprite(im, "wili_idle_side", 0, pos, opacity=fade*(.7-.12*k), ghost=True)
            layer = Image.new("RGBA", im.size)
            d = ImageDraw.Draw(layer)
            for n in range(3):
                y = start[1]-55-n*38
                d.line([(start[0], y+18), (end[0], y-8)], fill=(154,198,245,round(110*fade)), width=3-n)
            im.alpha_composite(layer)


def impact(im,t):
    for when,pos,target in ATTACKS:
        local=t-(when+.33)
        if 0<=local<.20:
            p=local/.20
            x,y=HOUNDS[target]
            layer=Image.new("RGBA",im.size)
            d=ImageDraw.Draw(layer)
            alpha=round(210*(1-p))
            # A short editorial hit accent, never a fake damage number.
            d.line([(x-38,y-134),(x+38,y-55)],fill=(237,242,234,alpha),width=max(1,round(7*(1-p))))
            d.line([(x-16,y-62),(x+15,y-120)],fill=(148,199,245,alpha),width=3)
            im.alpha_composite(layer)


@lru_cache(maxsize=10)
def gem_image(name):
    im=Image.open(NATIVE / (name+".png")).convert("RGBA")
    im.thumbnail((63,63),Image.Resampling.LANCZOS)
    return im


def gems(im,t):
    for when,name,start,end in [(1.14,"redgem",(505,795),(555,895)),(2.58,"purplegem",(825,795),(860,908))]:
        local=t-when
        if local < 0:
            continue
        p=min(1.,local/.65)
        x,y=interpolate(start,end,p)
        y-=82*math.sin(p*math.pi)
        alpha=1. if t<5.65 else max(0.,(6.1-t)/.45)
        sprite=gem_image(name)
        if alpha<1:
            sprite=sprite.copy()
            sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a*alpha)))
        shadow(im,(x,end[1]),60,round(75*alpha))
        im.alpha_composite(sprite,(round(x-sprite.width/2),round(y-sprite.height)))
        if .2<local<.8:
            d=ImageDraw.Draw(im)
            sx,sy=x+25,y-sprite.height-8
            strength=math.sin((local-.2)/.6*math.pi)*7
            d.line([(sx-strength,sy),(sx+strength,sy)],fill=PAPER,width=2)
            d.line([(sx,sy-strength),(sx,sy+strength)],fill=PAPER,width=2)


def caption(im,t):
    if t<2.1:
        label="瞬移突袭"
    elif t<3.65:
        label="挥刀生宝"
    elif t<5.1:
        label="穿梭敌阵"
    else:
        label="银月弯刀"
    d=ImageDraw.Draw(im)
    text_center(d, 916, label, 39, PAPER)
    text_center(d, 971, "专武攻击 · 概率掉落宝石", 22, FROST, "small")


def render(t, base):
    im=base.copy()
    for i,pos in enumerate(HOUNDS):
        name="hound_idle"
        idx=int(t*15+i*3)
        for when,_,target in ATTACKS:
            local=t-(when+.33)
            if target==i and 0<=local<13/30:
                name="hound_hit"
                idx=min(12,int(local*30))
        shadow(im,pos,145,100)
        put_sprite(im,name,idx,pos,scale=.235,mirror=True)
    warp_trails(im,t)
    name,idx,pos,alpha=actor_state(t)
    shadow(im,pos,95,round(110*alpha))
    put_sprite(im,name,idx,pos,opacity=alpha)
    impact(im,t)
    gems(im,t)
    caption(im,t)
    return im.convert("RGB")


def global_palette(frames, colors):
    samples=frames[::5]
    sheet=Image.new("RGB",(256,256*len(samples)))
    for i,im in enumerate(samples):
        sheet.paste(im.resize((256,256)),(0,256*i))
    # The tiny gems must not lose their colors to the much larger blue backdrop.
    # Reserve 16 native red and 16 native purple swatches in every frame palette.
    background_colors=colors-32
    main=sheet.quantize(colors=background_colors,method=Image.Quantize.MEDIANCUT)
    swatches=main.getpalette()[:background_colors*3]
    for name in ("redgem","purplegem"):
        gem=Image.open(NATIVE / (name+".png")).convert("RGBA")
        rgb=Image.new("RGB",gem.size,(42,48,63))
        rgb.paste(gem,mask=gem.getchannel("A"))
        sample=rgb.quantize(colors=16,method=Image.Quantize.MEDIANCUT)
        swatches.extend(sample.getpalette()[:48])
    result=Image.new("P",(1,1))
    result.putpalette(swatches+[0]*(768-len(swatches)))
    return result


def write_gif(frames,path,size,colors=192,duration_ms=80):
    resized=[im.resize((size,size),Image.Resampling.LANCZOS) for im in frames]
    palette=global_palette(resized,colors)
    indexed=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in resized]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=duration_ms,loop=0,optimize=True,disposal=1)
    return path.stat().st_size


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--stills-only",action="store_true")
    args=parser.parse_args()
    out=ROOT
    out.mkdir(exist_ok=True)
    base=base_art()
    peak=render(2.56,base)
    peak.save(out / "wili-cover.png")
    snapshots=[.16,.64,1.12,1.6,2.16,2.56,3.04,3.84,4.16,5.36]
    board=Image.new("RGB",(1600,680),(19,25,37))
    for i,t in enumerate(snapshots):
        frame=render(t,base).resize((320,320),Image.Resampling.LANCZOS)
        x,y=(i%5)*320,(i//5)*340
        board.paste(frame,(x,y))
        ImageDraw.Draw(board).text((x+8,y+321),f"{t:.2f}s",font=font(13,"small"),fill="white")
    board.save(out / "storyboard.png")
    peak.resize((256,256),Image.Resampling.LANCZOS).save(out / "thumbnail-256.png")
    if args.stills_only:
        return
    # Start on an action moment so paused storefront thumbnails still tell a story.
    offset=32
    times=[((i+offset)%TOTAL)/FPS for i in range(TOTAL)]
    frames=[render(t,base) for t in times]
    outputs={}
    path=out / "wili-cover-hq.gif"
    byte_count=write_gif(frames,path,768,224)
    outputs[path.name]={"width":768,"height":768,"bytes":byte_count,"frames":TOTAL,"duration_ms":6400,"palette_colors":224}
    print(path.name,byte_count,flush=True)
    compact_frames=[render(((i+25)%64)/10,base) for i in range(64)]
    for size,colors in [(512,112),(480,112),(448,96),(432,96)]:
        path=out / "wili-cover.gif"
        byte_count=write_gif(compact_frames,path,size,colors,100)
        outputs[path.name]={"width":size,"height":size,"bytes":byte_count,"frames":64,"duration_ms":6400,"palette_colors":colors}
        print("compatibility",size,colors,byte_count,flush=True)
        if byte_count<1_000_000:
            break
    checks={"render_kind":"promotional reconstruction, not recorded gameplay","runtime_modified":False,"image_generator":"built-in image_gen","outputs":outputs,"source_manifests":["generation-prompt.json","native-manifest.json"]}
    (out / "export-report.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
