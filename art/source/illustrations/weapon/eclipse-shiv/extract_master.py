"""Extract the large left-hand Eclipse Shiv from the supplied design sheet."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


OUT=Path(__file__).resolve().parent
SOURCE=OUT/"eclipse-shiv-reference.png"


def remove_callouts(image):
    """Restore just the two crossed areas by following nearby original texture."""
    rgb=np.asarray(image,dtype=np.float64).copy()
    h,w=rgb.shape[:2]
    y,x=np.mgrid[:h,:w]
    mask=np.zeros((h,w),dtype=bool)
    # Both marks have a black center and a fine paper-white keyline.
    for start,end,dot,radius,width in (
        ((611,237.7),(657.2,269.3),(657.2,269.3),6.65,3.20),
        ((336.7,615.3),(423,678.5),(336.7,615.3),7.1,3.90)):
        vx,vy=end[0]-start[0],end[1]-start[1]
        u=np.clip(((x-start[0])*vx+(y-start[1])*vy)/(vx*vx+vy*vy),0,1)
        d=np.hypot(x-start[0]-u*vx,y-start[1]-u*vy)
        mask|=(d<=width)|(np.hypot(x-dot[0],y-dot[1])<=radius)
    yy,xx=np.nonzero(mask)
    candidates=[]
    costs=[]
    for theta in np.linspace(0,math.pi,24,endpoint=False):
        dx,dy=math.cos(theta),math.sin(theta)
        ends=[]
        for sign in (-1,1):
            hit=np.zeros(len(xx),dtype=bool)
            distances=np.full(len(xx),40)
            colors=np.zeros((len(xx),3))
            for step in range(1,40):
                sx=np.rint(xx+sign*dx*step).astype(int)
                sy=np.rint(yy+sign*dy*step).astype(int)
                select=(~hit)&(~mask[sy,sx])
                distances[select]=step
                colors[select]=rgb[sy[select],sx[select]]
                hit|=select
            ends.append((distances[:,None],colors))
        (d1,c1),(d2,c2)=ends
        total=d1+d2
        mid=(c1*d2+c2*d1)/total
        cost=np.mean(np.abs(c1-c2),axis=1)+total[:,0]*.81
        cost+=(total[:,0]>38)*150
        candidates.append(mid)
        costs.append(cost)
    costs=np.stack(costs)
    weights=np.exp(-(costs-costs.min(axis=0))/3.7)
    fill=(np.stack(candidates)*weights[:,:,None]).sum(axis=0)/weights.sum(axis=0)[:,None]
    # The coordinate hash supplies faint deterministic paper grain without
    # imprinting the broad dark leader or smearing the restored eye area.
    grain=1.8*np.sin(xx*9.32+yy*17.71)
    rgb[yy,xx]=np.clip(fill+grain[:,None],0,255)
    return Image.fromarray(np.rint(rgb).astype(np.uint8)),mask


def outline(repaired):
    arr=np.asarray(repaired)
    gray=np.mean(arr,axis=2)
    region=Image.new("1",repaired.size)
    ImageDraw.Draw(region).polygon(
        [(52,930),(46,827),(150,690),(188,674),(184,610),(275,520),
         (274,478),(385,390),(387,363),(473,287),(561,283),(626,220),
         (689,152),(704,78),(724,81),(732,195),(730,313),(691,398),
         (621,500),(525,585),(438,665),(404,676),(391,757),
         (313,767),(256,805),(181,890),(101,930)],fill=1)
    dark=Image.fromarray(((gray<130)&np.asarray(region))*np.uint8(255)).copy()
    # Keep the single contiguous ink contour. Detached shard decorations,
    # drop shadow, labels and registration marks on the sheet are independent.
    ImageDraw.floodfill(dark,(471,361),158)
    connected=np.asarray(dark)==158
    wall=Image.fromarray(connected.astype(np.uint8)*255)
    # The thin black rim is closed again where the two old leaders crossed.
    wall=wall.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    # Fill all material inside the perimeter while preserving the intentional
    # paper-coloured through-hole in the butt of the wrapped handle.
    ImageDraw.floodfill(wall,(0,0),128)
    ImageDraw.floodfill(wall,(107,851),128)
    filled=(np.asarray(wall)!=128)
    return Image.fromarray(filled.astype(np.uint8)*255)


def antialias(repaired,silhouette):
    rgb=np.asarray(repaired).astype(float)
    alpha=np.asarray(silhouette).astype(float)/255
    inside=np.asarray(silhouette.filter(ImageFilter.MinFilter(3))).astype(float)/255
    nearby=np.asarray(silhouette.filter(ImageFilter.MaxFilter(3))).astype(float)/255
    # The antique paper is warm and almost flat; measure its local RGB in a
    # small window, then unmatte only the perimeter. Interior pixels stay exact.
    keep=(alpha==0)&(rgb[:,:,0]>140)&(rgb[:,:,0]>rgb[:,:,2]+12)
    weight=np.asarray(Image.fromarray(np.uint8(keep)*255).filter(ImageFilter.GaussianBlur(5)))/255
    paper=np.stack([np.asarray(Image.fromarray(np.uint8(rgb[:,:,c]*keep))
                               .filter(ImageFilter.GaussianBlur(5))).astype(float)/np.maximum(weight,.01)
                    for c in range(3)],axis=-1)
    paper=np.where((weight<.05)[:,:,None],(194,178,159),paper)
    gray=rgb.mean(axis=2);back=paper.mean(axis=2)
    coverage=np.clip((back-gray-5)/np.maximum(back-30,1),0,1)
    a=np.maximum(inside,nearby*coverage)
    ink=(rgb-(1-a[:,:,None])*paper)/np.maximum(a[:,:,None],1e-6)
    ink=np.where((a>0)[:,:,None],np.clip(ink,0,255),0)
    return Image.fromarray(np.uint8(np.rint(np.dstack((ink,a*255)))))


def main():
    with Image.open(SOURCE) as source:
        image=source.convert("RGB")
    assert image.size==(1536,1024)
    repaired,_=remove_callouts(image)
    master=antialias(repaired,outline(repaired))
    master.save(OUT/"master.png")
    data=dict(image="master.png",source=SOURCE.name,canvas=list(image.size),units="source pixels, origin top-left",
              grip=[175,758],tip=[710,91],pommel=[74,916],guard=[220,700],
              wrap_start=[128,813],wrap_end=[221,698],eye_center=[313,616],
              ring_hole_center=[107,851],blade_root=[373,643],
              source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    dx,dy=np.subtract(data["wrap_end"],data["wrap_start"])
    data["handle_axis_toward_blade"]=[round(dx/math.hypot(dx,dy),6),round(dy/math.hypot(dx,dy),6)]
    data["handle_angle_degrees_screen"]=round(math.degrees(math.atan2(dy,dx)),3)
    (OUT/"registration.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
