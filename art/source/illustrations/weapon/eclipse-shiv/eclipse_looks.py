"""Render the Eclipse Shiv directly from its supplied four-phase character sheet.

The 1536 x 1024 registered result retains master.png's handle and outline.
weapon(phase_id, state="balanced", time=0.0) accepts time in seconds.
"""
from functools import lru_cache
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
PERIOD, FRAMES = 1.2, 30
SIZE = (1536,1024)
METAL = (192,78,735,750)
CROP = (0,45,744,950)
PREVIEW = (372,453)

PHASES = ("new","waxing_quarter","waxing_half","waxing_threequarter","full","waning_threequarter","waning_half","waning_quarter")
NAMES = ("新月","蛾眉月","上弦","盈凸月","满月","亏凸月","下弦","残月")
# The four named frames are the artist's four actual paintings, in order.
CORNERS = ("new","wax","full","wane")
MIX = ((0,0,0.),(0,1,.52),(1,1,0.),(1,2,.52),(2,2,0.),(2,3,.50),(3,3,0.),(3,0,.50))
LIGHT = (.03,.28,.56,.8,1.,.73,.42,.20)

# Crown, tip, cutting-side notches, shadow-spine hooks, phase eye and grip.
# Matching landmarks map large master pixels back to the small painted blades.
LARGE = np.array([
 (710,91),(718,256),(692,343),(585,513),(403,639),(375,744),
 (313,616),(268,647),(360,587),(257,560),(294,477),(376,418),
 (384,449),(394,373),(505,306),(519,346),(595,287),(658,225),
 (72,916),(195,679),(260,719),(501,483),(590,354),
],dtype=np.float64)
NEW = np.array([
 (1093,143),(1085,204),(1069,244),(1018,305),(952,345),(953,374),
 (914,336),(894,347),(936,322),(889,315),(905,285),(945,262),
 (952,275),(956,248),(994,224),(1001,235),(1022,220),(1050,202),
 (798,458),(859,354),(889,382),(988,302),(1029,240),
],dtype=np.float64)
WAX = NEW + np.array([
 (403,-1),(405,1),(404,2),(402,3),(401,1),(402,0),(401,-1),(401,0),
 (400,-1),(400,-1),(400,0),(403,0),(402,0),(402,-1),(403,0),(401,1),
 (403,1),(402,3),(402,0),(401,0),(401,0),(401,0),(400,0),
])
FULL = NEW + np.array([
 (3,408),(3,411),(6,410),(4,412),(2,411),(1,413),(1,414),(1,413),
 (2,413),(0,411),(2,409),(0,408),(0,409),(3,399),(4,407),(7,406),
 (6,408),(0,420),(2,419),(1,411),(1,412),(2,411),(4,411),
])
WANE=FULL + np.array([
 (400,2),(400,0),(-1+400,-1),(399,0),(399,0),(399,1),(400,0),(399,0),
 (400,1),(400,2),(400,2),(400,2),(400,2),(400,4),(400,2),(400,2),
 (397,0),(399,0),(400,0),(400,0),(400,0),(399,0),(399,0),
])

def clamp(x):
    return np.clip(x,0,1)

def ease(x):
    a=clamp(x)
    return a*a*(3-2*a)

def cel_index(seconds):
    return int(math.floor((seconds%PERIOD)/PERIOD*FRAMES+1e-7))%FRAMES

def _kernel(d):
    return d*np.log(d+1e-13)

def register(target):
    # A regularized thin-plate spline preserves the hooked silhouette while
    # following the artist's small differences in pose and facet placement.
    p=(LARGE-[448.,413.])/225.
    diff=p[:,None,:]-p[None,:,:]
    radial=_kernel(np.sum(diff*diff,axis=-1)) + np.eye(len(p))*.00062
    affine=np.c_[np.ones(len(p)),p]
    mat=np.block([[radial,affine],[affine.T,np.zeros((3,3))]])
    fit=np.linalg.solve(mat,np.vstack([target,np.zeros((3,2))]))
    x0,y0,x1,y1=METAL
    maps=[]
    for row in range(y0,y1,32):
        yy,xx=np.mgrid[row:min(row+32,y1),x0:x1]
        pts=np.column_stack((xx.ravel(),yy.ravel()))
        norm=(pts-[448.,413.])/225.
        k=_kernel(np.sum((norm[:,None,:]-p[None,:,:])**2,axis=-1))
        mapped=k@fit[:-3]+np.c_[np.ones(len(norm)),norm]@fit[-3:]
        maps.append(mapped.reshape((*xx.shape,2)).astype(np.float32))
    return np.concatenate(maps)

def sample(arr,coord):
    x,y=coord[...,0],coord[...,1]
    ix=x.astype(np.int32).clip(0,arr.shape[1]-2)
    iy=y.astype(np.int32).clip(0,arr.shape[0]-2)
    dx,dy=(x-ix)[...,None],(y-iy)[...,None]
    return ((1-dy)*((1-dx)*arr[iy,ix]+dx*arr[iy,ix+1])+
            dy*((1-dx)*arr[iy+1,ix]+dx*arr[iy+1,ix+1])).astype(np.float32)

@lru_cache(maxsize=1)
def master():
    image=Image.open(ROOT/"master.png").convert("RGBA")
    bbox=image.getchannel("A").point(lambda v:255 if v>127 else 0).getbbox()
    if image.size!=SIZE or not bbox or bbox[2]-bbox[0]<620:
        raise ValueError("Eclipse Shiv master needs its source-registered silhouette")
    return image

@lru_cache(maxsize=1)
def geometry():
    im = master().crop(METAL)
    v=np.asarray(im).astype(np.float32)
    x0,y0,x1,y1=METAL
    y,x=np.mgrid[y0:y1,x0:x1].astype(np.float32)
    rgb=v[:,:,:3];lum=rgb@np.array((.253,.60,.147),np.float32)
    # Root to tip longitudinal map. Direction is unambiguous on all facets
    # and the same registration is used for the loose shards and light slivers.
    lungo=np.clip(((x-329)*.606-(y-633)*.797)/667.,0,1)
    transverse=(x-329)*.797+(y-633)*.606
    mask=(v[:,:,3]/255.)
    eye=np.array([[264,650],[276,629],[292,610],[311,599],[332,593],[367,584],[357,607],[342,624],[321,637],[294,644]])
    eye_m=Image.new("L",im.size)
    ImageDraw.Draw(eye_m).polygon([tuple(a-[x0,y0]) for a in eye],fill=255)
    eye_m=np.asarray(eye_m.filter(ImageFilter.GaussianBlur(.8)),dtype=np.float32)/255
    guard_m=ease(((x-235)*.70-(y-657)*.72+38)/41)
    fine=lum-np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(3.3)),dtype=np.float32)
    # Physical steel faces reflect the reference lighting; the black silhouette
    # and the dark live-shadow spine retain the original drawing and its cuts.
    facet=ease((lum-45)/57)*mask*guard_m
    spine_reflect=ease((lum-19)/52)*mask*guard_m
    return rgb,lum,mask,facet,spine_reflect,eye_m,fine,lungo,transverse,x,y

@lru_cache(maxsize=1)
def registered_paint():
    board=Image.open(ROOT/"eclipse-shiv-reference.png").convert("RGB")
    # A light median lift removes duplicated tiny ink cracks from the small
    # originals. Crack structure, highlights and grain come from the master.
    broad=np.asarray(board.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.05)),dtype=np.float32)
    rgb,lum,mask,facet,spine,eye,fine,u,v,x,y=geometry()
    result=[]
    for j,target in enumerate((NEW,WAX,FULL,WANE)):
        mapped=sample(broad,register(target))
        # Avoid parchment fringes when registration strays across the silhouette.
        warm=(mapped[:,:,0]-mapped[:,:,2]>22)&(mapped[:,:,0]-mapped[:,:,1]>7)&(mapped[:,:,0]>142)
        neutral=np.mean(mapped,axis=2,keepdims=True)
        mapped=np.where(warm[...,None],neutral+np.array((0.,1.,-1.)),mapped)
        # Limit the dark register on a high-valued master facet: the reference
        # line is a colour guide, not a second ink outline superimposed on it.
        ref_l=mapped@np.array((.253,.60,.147),dtype=np.float32)
        floor=np.interp(lum,(30,78,108,149,192,243),(12,25,35,50,62,72)).astype(np.float32)
        if j!=0:
            floor+=(lum/255)**2 * (52 if j==2 else 22)
        mapped += np.maximum(0,floor-ref_l)[...,None]
        # Retain every line and fine scratch drawn on the large original.
        grain=np.clip(fine,-65,29)[...,None]
        mapped += grain*(.44 if j==0 else .71)
        # Different references change the inner live-shadow facets as well as
        # the bright crystal. The decorated handle/collar stays in its own art.
        interior=facet+(1-facet)*.20*spine
        # At all phases black structural ink remains black.
        interior*=ease((lum-15)/24)
        crystal=rgb+(mapped-rgb)*interior[...,None]
        # The phase eye has its own response. Restore the large iris shape
        # and tiny central glint after registering its illumination.
        eye_cols=((117,110,132),(205,218,200),(246,244,211),(166,163,168))
        ec=np.array(eye_cols[j])
        iris=np.exp(-(((x-309)/18.4)**2+((y-617)/17.5)**2)*1.55)
        catch=np.exp(-(((x-319)/5.8)**2+((y-610)/6.2)**2)*1.65)
        eyed=ec+(lum-186)[...,None]*(.33 if j==0 else .54)
        eyed-=iris[...,None]*np.array((32,36,34));eyed+=catch[...,None]*np.array((46,46,39))
        em=eye*ease((lum-62)/54)*mask
        crystal+=(eyed-crystal)*em[...,None]
        result.append(np.uint8(np.rint(np.clip(crystal,0,255))))
    return result

@lru_cache(maxsize=8)
def surface(phase_id):
    j=PHASES.index(phase_id); l,r,t=MIX[j]
    views=registered_paint()
    rgb=views[l] if l==r else np.rint(views[l].astype(np.float32)*(1-t)+views[r]*t).astype(np.uint8)
    im=master().copy()
    patch=np.asarray(im.crop(METAL)).copy();patch[:,:,:3]=rgb
    im.paste(Image.fromarray(patch),METAL[:2])
    return im

def arc_polyline(points,u):
    p=np.asarray(points,dtype=np.float64)
    distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    ratio=np.clip(u,0,1)*distance[-1]
    j=np.searchsorted(distance,ratio,side="right")-1
    j=min(max(0,j),len(p)-2)
    tangent=p[j+1]-p[j];tangent=tangent/np.linalg.norm(tangent)
    result=p[j]+tangent*(ratio-distance[j])
    return result,tangent

SPINE=((230,593),(263,540),(308,491),(364,428),(412,379),(484,322),(540,291),(588,267),(641,225),(683,171),(710,101))
EDGE=((368,646),(417,606),(468,558),(521,527),(581,508),(622,442),(660,360),(690,330),(712,251),(720,180),(711,101))
OFF=(.07,.61,.31,.84,.46,.95,.17,.70)
SEA=(167,201,179); IVORY=(242,240,209)
VIOLET=(111,102,122); VOID=(42,37,41)
FXBOX=(118,60,744,762)
FXOR=np.array(FXBOX[:2],dtype=float)

@lru_cache(maxsize=2)
def cut_flake(pale):
    # Cut the actual hollow glass lozenge and void flake from the two supplied
    # reference panels. Their irregular edges and ink are the design itself.
    board=Image.open(ROOT/"eclipse-shiv-reference.png").convert("RGBA")
    if pale:
        points=np.array(((893.8,672.1),(897.2,651.6),(919.1,637.8),(912.0,658.7)))
        color=(163,202,169)
    else:
        points=np.array(((1048.4,304.2),(1051.7,294.0),(1064.1,287.4),(1059.8,298.0)))
        color=(53,45,50)
    box=(math.floor(points[:,0].min())-2,math.floor(points[:,1].min())-2,
         math.ceil(points[:,0].max())+3,math.ceil(points[:,1].max())+3)
    area=board.crop(box)
    mat=Image.new("L",(area.width*4,area.height*4))
    ImageDraw.Draw(mat).polygon([tuple((q-box[:2])*4) for q in points],fill=255)
    area.putalpha(mat.resize(area.size,Image.Resampling.LANCZOS))
    center=(points[0]+points[2])*.5-np.array(box[:2])
    axis=points[2]-points[0]
    half=np.linalg.norm(axis)*.5;axis/=2*half
    return area.convert("RGBa"),center,axis,half

def shard(tile,center,tangent,radius,width,pale,opacity,reverse=False):
    im,pivot,src,src_radius=cut_flake(pale)
    dst=np.asarray(tangent)*(-1 if reverse else 1)
    norm=np.array((dst[1],-dst[0]))
    basis=np.column_stack((dst,norm))
    source=np.column_stack((src,(src[1],-src[0])))
    transform=basis@np.diag((radius/src_radius,(width/.44)/src_radius))@source.T
    inv=np.linalg.inv(transform)
    size=math.ceil(radius*2+width*2+5)
    mid=np.array((size*.5,size*.5))
    offset=pivot-inv@mid
    im=im.transform((size,size),Image.Transform.AFFINE,(*inv[0],offset[0],*inv[1],offset[1]),Image.Resampling.BICUBIC).convert("RGBA")
    if opacity<255:
        im.putalpha(im.getchannel("A").point(lambda a:a*opacity/255))
    dest=np.rint(np.asarray(center)-FXOR-mid).astype(int)
    tile.alpha_composite(im,tuple(dest))

def atmosphere(phase_id,n):
    j=PHASES.index(phase_id); lum=LIGHT[j];t=n/FRAMES
    layer=Image.new("RGBA",(FXBOX[2]-FXBOX[0],FXBOX[3]-FXBOX[1]))
    dr=ImageDraw.Draw(layer)
    # Seven narrow glass slivers are visible at full moon. At new moon there
    # are only a few dark scales and a live-shadow wisp along the spine notch.
    count=(4,4,6,7,8,6,5,4)[j]
    for k in range(count):
        progress=(t+OFF[k])%1
        strength=math.sin(math.pi*progress)**.56
        if j in (1,2,3):
            u=.04+.92*progress
            spread=(61+16*(k%3))*(1-progress)**.76+1
        elif j in (5,6,7):
            u=.94-.89*progress
            spread=(48+17*(k%3))*(1-progress)**.7+2
        elif j==4:
            u=(.14,.39,.55,.77,.88,.69,.28,.49)[k]+.026*math.sin(math.tau*progress)
            spread=(35+22*(k%3))+(9+3*(k%2))*math.sin(math.tau*progress)
            strength=.63+.37*strength
        else:
            u=(.23,.51,.83,.61)[k]+.045*progress
            spread=22+40*progress
        left=(k%3!=1)
        p,tan=arc_polyline(SPINE if left else EDGE,u)
        per=np.array((tan[1],-tan[0]))*(1 if left else -1)
        # Avoid grazing the frame at the extreme outer tip.
        if not left: spread*=.45+.5*(1-u)
        p+=per*spread
        r=((11+21*lum)*(1+.23*((k%3)-1)))*(.56+.44*strength)
        if j==0:r*=.94
        p[0]=min(p[0],CROP[2]-4-r)
        pale=(j==4 or (j<=3 and k<round(count*(.27+.54*lum))) or (j>=5 and k%4==1))
        shard(layer,p,tan,r,r*(.44 if pale else .41),pale,round(246*strength),j>=5)
        # Two staggered tiny echoes extend along the exact flight path. They
        # make the direction readable without adding drawn arrows or a halo.
        if j in (1,2,3,5,6,7) and k in (0,2,4):
            for z in (1,2):
                tip=p+tan*((-1 if j<4 else 1)*(z*7+r))
                shard(layer,tip,tan,r*(.38/z),r*.17/z,pale,round(150*strength/z),j>=5)
    if j in (0,7):
        t0=math.tau*t
        path=((206,538),(216,521),(211,502),(217,483),(234,468),(268,454),
              (283,440),(292,423),(305,417),(333,414),(344,407))
        coords=[]
        side=[]
        for h in np.linspace(0,1,47):
            point,head=arc_polyline(path,h)
            normal=np.array((head[1],-head[0]))
            sway=4.5*math.sin(t0-6*h)*math.sin(math.pi*h)
            position=point+normal*sway-FXOR
            width=(2+8*(1+math.sin(3.5*math.pi*h-.4))*.5)*math.sin(math.pi*h)**.63
            if j==7:width*=.59
            coords.append(position);side.append(position+normal*width)
        dr.polygon([tuple(z) for z in coords+side[::-1]],fill=(43,37,44,239 if j==0 else 157))
    return layer

@lru_cache(maxsize=8)
def pulse_geometry(phase_id):
    _,_,_,facet,_,eye,_,u,norm,x,y=geometry()
    # The three broken lanes follow changes in the original crystal's facet
    # structure. Restrict to existing crystal to preserve all ink boundaries.
    gu=np.array((.0,.12,.22,.37,.53,.69,.84,1.))
    center=np.interp(u,gu,(-9,4,7,-2,0,1,-5,0))
    lane=norm-center
    widths=(4.8,5.8,4.2)
    mid=(17+12*np.sin(u*5.2),55-18*u,-19+8*np.sin(5.5*u+.5))
    veins=[np.exp(-((lane-m)/w)**2)*facet*ease((u-.035)/.07)*ease((1.0-u)/.07) for m,w in zip(mid,widths)]
    return u,[np.float32(v) for v in veins]

@lru_cache(maxsize=1)
def full_halo():
    a=master().crop(METAL).getchannel("A")
    edge=a.filter(ImageFilter.MaxFilter(23)).filter(ImageFilter.GaussianBlur(5))
    u=geometry()[7]
    y,x=np.indices(u.shape)
    fade=ease((u.shape[1]-1-x)/9)*ease(y/8)
    return np.asarray(edge,dtype=np.float32)*ease((u-.045)/.36)*fade

@lru_cache(maxsize=6)
def _weapon(phase_id,n):
    j=PHASES.index(phase_id);t=n/FRAMES
    surface_im=surface(phase_id)
    base=Image.new("RGBA",SIZE)
    if j==4:
        # Soft bloom only hugs the jagged cutting end, exactly as in the
        # reference full-moon panel. No ring surrounds the blade.
        al=full_halo()*(.37+.04*math.sin(math.tau*t))
        color=Image.new("RGBA",(METAL[2]-METAL[0],METAL[3]-METAL[1]),(171,212,179));color.putalpha(Image.fromarray(np.uint8(al)))
        base.paste(color,METAL[:2])
    base.alpha_composite(atmosphere(phase_id,n),FXBOX[:2])
    patch=np.array(surface_im.crop(METAL))
    u,lanes=pulse_geometry(phase_id)
    beam=np.zeros_like(u)
    # Phase differences are directly legible on the metal in the absence of
    # loose particles: positive longitudinal motion for waxing, negative for waning.
    for k,ink in enumerate(lanes):
        p=(t+(0,.38,.73)[k])%1
        center=(1-p) if j>=5 else p
        band=np.exp(-((u-center)/(.085 if j==4 else .068))**2)
        beam+=band*ink*(math.sin(math.pi*p)**.32)
    colors=np.array((224,245,216)) if j<=4 else np.array((197,218,203))
    strength=(.13,.60,.86,.88,.48,.85,.84,.46)[j]
    col=patch[:,:,:3].astype(np.float32)
    col+=(colors-col)*np.clip(beam*strength,0,1)[...,None]
    patch[:,:,:3]=np.uint8(np.rint(np.clip(col,0,255)))
    im=surface_im.copy();im.paste(Image.fromarray(patch),METAL[:2])
    base.alpha_composite(im)
    return base

def weapon(phase_id,state="balanced",time=0.0):
    """Registered independent frame, natural lunar influence, seconds."""
    if state not in ("balanced","natural",None):
        raise ValueError("This reference has one natural allegiance per moon phase")
    return _weapon(phase_id,cel_index(time)).copy()
