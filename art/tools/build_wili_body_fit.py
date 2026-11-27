"""Retain Wilson's animation names/timing while adjusting Wili's visual proportions.

The body is 1.10x; head artwork and held objects retain their dimensions.
Normal held idle/running closes the elbow five degrees and shortens its forearm 6%.
Worn hats (swap_hat frames 0-2) are seated +22 local-Y units lower to match Wili's head proportions.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse,hashlib,json,math,re,struct
import numpy as np

import render_workshop_native as rig
from build_wili_scimitar_attack import serialize

ROOT=Path(__file__).resolve().parents[2]
BANK='wili_body_fit'
BODY_SCALE=1.10
CARRY_ANGLE=5.
CARRY_FOREARM_SCALE=.94
FRONT_HEAD_OFFSET=-3.5
HAT_LOCAL_Y_OFFSET=22.
REST_CLIPS={'idle_loop','run_pre','run_loop','run_pst'}
HEAD={'headbase','headbase_hat','face','cheeks','hair','hair_hat','hairfront','hairpigtails',
      'beard','beard_skin','swap_hat','swap_face','swap_hat_helmet','swap_hat_top'}
BODY={'torso','torso_skin','torso_pelvis','arm_upper','arm_upper_skin','arm_lower',
      'arm_lower_skin','arm_lower_cuff','hand','hand_skin','leg','leg_skin','foot',
      'foot_skin','swap_body','swap_body_tall','swap_backpack','swap_shoulder','swap_arm'}


def scan(data):
    """Read the clip catalog without constructing every element dictionary."""
    magic,version,_,_,_,count=struct.unpack_from('<4s5I',data)
    assert magic==b'ANIM' and version==4
    p=24;rows=[]
    for index in range(count):
        n,=struct.unpack_from('<I',data,p);p+=4
        name=data[p:p+n].decode('utf8');p+=n
        facing,root,fps,frames=struct.unpack_from('<BIfI',data,p);p+=13
        for _ in range(frames):
            p+=16
            events,=struct.unpack_from('<I',data,p);p+=4+events*4
            elems,=struct.unpack_from('<I',data,p);p+=4+elems*40
        rows.append((index,name,facing,root,fps,frames))
    return rows


def source_order():
    wanted=rig.pipeline.hash_name('wilson');available=[]
    for path in sorted(rig.GAME.glob('*.zip')):
        with ZipFile(path) as z:
            if 'anim.bin' not in z.namelist():continue
            if any(row[3]==wanted for row in scan(z.read('anim.bin'))):available.append(path.name)
    # Native general-player declarations take precedence over unused authoring
    # reference cels and older duplicate useitem drawings in specialty packs.
    primary=[]
    with ZipFile(rig.GAME.parent/'databundles/scripts.zip') as z:
        for script in ('scripts/prefabs/global.lua','scripts/prefabs/player_common.lua'):
            s=re.sub(r'--[^\n]*','',z.read(script).decode('utf8'))
            primary.extend(re.findall(r'Asset\(\s*"ANIM"\s*,\s*"anim/([^\"]+)"\s*\)',s))
    paths=[rig.GAME/n for n in available if n not in primary]
    paths += [rig.GAME/n for n in dict.fromkeys(primary) if n in available]
    paths.append(ROOT/'anim/wili_scimitar_attack.zip')
    return paths


def xy(e):return np.asarray(e['matrix'][4:6],dtype=float)


def basis(e):
    a,b,c,d=e['matrix'][:4]
    return np.array(((a,c),(b,d)))


def store(e,b,p):e['matrix'][:6]=[b[0,0],b[1,0],b[0,1],b[1,1],p[0],p[1]]


def head_symbol(name):
    return name in HEAD or name.startswith(('swap_hat_','swap_face_','beard_','hair_'))


def hat_offset(element,symbol_name,offset=HAT_LOCAL_Y_OFFSET):
    """Seat worn hats lower onto Wili's head without shifting ground bush-hat hides."""
    if symbol_name=='swap_hat' and element['frame'] in (0,1,2):
        return basis(element)@np.array((0.,offset))
    return np.zeros(2)


def head_anchors(frames,names):
    # A few native disappearance/jump cels omit headbase while retaining a
    # face, hair or hat cel. Continue the same head-root translation through
    # those cels instead of suddenly dropping the offset to zero.
    found={}
    for i,frame in enumerate(frames):
        head=next((e for e in frame['elements'] if names[e['symbol']].lower()=='headbase'),None)
        if head is None:head=next((e for e in frame['elements'] if names[e['symbol']].lower()=='headbase_hat'),None)
        if head:found[i]=xy(head)
    if not found:return [None]*len(frames)
    keys=list(found);values=np.array(list(found.values()));times=np.arange(len(frames))
    return np.column_stack([np.interp(times,keys,values[:,j]) for j in range(2)])


def head_offsets(frames,names):
    """Shift the frontal drawing and its attachments without redrawing the face."""
    found={}
    for i,frame in enumerate(frames):
        head=next((e for e in frame['elements'] if names[e['symbol']].lower()=='headbase'),None)
        if head is None:head=next((e for e in frame['elements'] if names[e['symbol']].lower()=='headbase_hat'),None)
        if head:
            found[i]=basis(head)@np.array((FRONT_HEAD_OFFSET,0.)) if head['frame'] in (0,3) else np.zeros(2)
    if not found:return np.zeros((len(frames),2))
    keys=list(found);values=np.array(list(found.values()));times=np.arange(len(frames))
    return np.column_stack([np.interp(times,keys,values[:,j]) for j in range(2)])


def transform(frame,names,anchor,close_elbow=False,head_anchor=None,head_offset=None):
    elements=frame['elements']
    def symbol(e):return names[e['symbol']].lower()
    def layer(e):return names[e['layer']].lower()
    head=next((e for e in elements if symbol(e)=='headbase'),None)
    if head is None:head=next((e for e in elements if symbol(e)=='headbase_hat'),None)
    head_at=xy(head) if head else head_anchor
    head_delta=(BODY_SCALE-1)*(head_at-anchor) if head_at is not None else np.zeros(2)
    if head_offset is not None:head_delta+=head_offset
    for e in elements:
        b,p=basis(e),xy(e)
        if head_symbol(symbol(e)):
            # Quantize head-group translation to float32 before adding hat_offset so
            # patching an existing wili_body_fit.zip stays bit-for-bit identical to
            # a full rebuild from native DST sources.
            p_head=np.asarray(p+head_delta,dtype=np.float32).astype(float)
            store(e,b,p_head+hat_offset(e,symbol(e)))
        elif symbol(e)=='swap_object' or layer(e)=='lantern_overlay':
            grip=np.array((0.,3. if e['frame']>=5 else 0.))
            store(e,b,anchor+BODY_SCALE*(p+b@grip-anchor)-b@grip)
        elif symbol(e) in BODY or symbol(e).startswith('swap_body_'):
            store(e,BODY_SCALE*b,anchor+BODY_SCALE*(p-anchor))
        else:
            # Instruments, books, shields, remotes and visual overlays are
            # attachments, not anatomy: their texture dimensions stay native.
            store(e,b,anchor+BODY_SCALE*(p-anchor))
    if close_elbow:
        arm={symbol(e):e for e in elements if layer(e)=='arm_carry'}
        if {'arm_upper','arm_lower','hand'}.issubset(arm):
            s,e,w=(xy(arm[k]) for k in ('arm_upper','arm_lower','hand'))
            u,v=s-e,w-e
            if min(np.linalg.norm(u),np.linalg.norm(v))>1e-7:
                angle=math.atan2(u[0]*v[1]-u[1]*v[0],np.dot(u,v))
                change=-math.copysign(min(math.radians(CARRY_ANGLE),abs(angle)),angle)
                c,si=math.cos(change),math.sin(change)
                turn=np.array(((c,-si),(si,c)))
                for element in elements:
                    if ((layer(element)=='arm_carry' and symbol(element) in {'arm_lower','arm_lower_cuff','hand','swap_object'})
                        or layer(element)=='lantern_overlay'):
                        store(element,turn@basis(element),e+turn@(xy(element)-e))
                # Shorten only the longitudinal elbow-to-wrist span. Keep the
                # sleeve width, fist and object scale, and translate the whole
                # grasp with its lantern/follower socket as one rigid unit.
                forearm=turn@v
                axis=forearm/np.linalg.norm(forearm)
                shorten=np.eye(2)+(CARRY_FOREARM_SCALE-1)*np.outer(axis,axis)
                wrist_shift=(CARRY_FOREARM_SCALE-1)*forearm
                for element in elements:
                    if layer(element)=='arm_carry' and symbol(element) in {'arm_lower','arm_lower_cuff'}:
                        store(element,shorten@basis(element),e+shorten@(xy(element)-e))
                    elif ((layer(element)=='arm_carry' and symbol(element) in {'hand','swap_object'})
                          or layer(element)=='lantern_overlay'):
                        store(element,basis(element),xy(element)+wrist_shift)
    # Conservative bounds; these do not change the physical position or hitbox.
    x,y,w,h=frame['bbox'];mid=anchor+BODY_SCALE*(np.array((x,y))-anchor)
    frame['bbox']=[mid[0],mid[1],w*BODY_SCALE+24,h*BODY_SCALE+24]


def ground_planes():
    table=rig.frame_lookup(rig.native_build((ROOT/'anim/wili.zip').resolve()))
    idle=rig.anim_archive('player_idles.zip')
    result={}
    for clip in idle['anims']:
        if clip['name']!='idle_loop':continue
        bottoms=[]
        for e in clip['frames'][0]['elements']:
            if idle['names'][e['symbol']]!='foot':continue
            rec=rig.get_frame(table,e['symbol'],e['frame']);im=rec['image']
            yy,xx=np.where(np.asarray(im.getchannel('A'))>=128)
            pts=np.vstack(((xx+.5)*rec['w']/im.width+rec['x']-rec['w']/2,
                          (yy+.5)*rec['h']/im.height+rec['y']-rec['h']/2))
            bottoms.append(float((basis(e)[1]@pts).max()+xy(e)[1]))
        result[clip['facing']]=max(bottoms)
    return result


def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    root=rig.pipeline.hash_name('wilson');selected={};sources=[]
    for path in source_order():
        with ZipFile(path) as z:data=z.read('anim.bin')
        rows=[row for row in scan(data) if row[3]==root]
        sources.append({'path':str(path),'sha256':hashlib.sha256(data).hexdigest()})
        for row in rows:selected[row[1],row[2]]=(path,row[0])
    groups={}
    for key,(path,index) in selected.items():groups.setdefault(path,set()).add(index)
    names={};records=bytearray();num_frames=num_elements=num_events=num_anims=0
    planes=ground_planes();catalog=[];newroot=rig.pipeline.hash_name(BANK)
    for path,indices in groups.items():
        bank=rig.anim_archive(path.name,path.parent);names.update(bank['names'])
        for index,c in enumerate(bank['anims']):
            if index not in indices:continue
            original=hashlib.sha256(serialize([c],{})).hexdigest()
            face=c['facing'];plane=planes.get(face,planes.get(5) if face in (1,4) else planes[8])
            anchors=head_anchors(c['frames'],bank['names'])
            offsets=head_offsets(c['frames'],bank['names'])
            for f,head_at,head_offset in zip(c['frames'],anchors,offsets):
                transform(f,bank['names'],np.array((0.,plane)),c['name'] in REST_CLIPS,head_at,head_offset)
                num_frames+=1;num_elements+=len(f['elements']);num_events+=len(f['events'])
            c['root']=newroot
            records.extend(serialize([c],{})[24:-4]);num_anims+=1
            catalog.append({'name':c['name'],'facing':face,'fps':c['fps'],'frames':len(c['frames']),
                            'source':path.name,'source_record_sha256':original})
    names[newroot]=BANK
    payload=struct.pack('<4s5I',b'ANIM',4,num_elements,num_frames,num_events,num_anims)+records+serialize([],names)[24:]
    (out/'anim.bin').write_bytes(payload)
    with ZipFile(out/(BANK+'.zip'),'w',ZIP_DEFLATED) as z:z.writestr('anim.bin',payload)
    manifest={'bank':BANK,'body_factor':BODY_SCALE,'head_size_factor':1.,'weapon_size_factor':1.,
              'held_elbow_degrees':CARRY_ANGLE,'held_forearm_scale':CARRY_FOREARM_SCALE,
              'frontal_head_local_x_offset':FRONT_HEAD_OFFSET,
              'hat_local_y_offset':HAT_LOCAL_Y_OFFSET,
              'elbow_clips':sorted(REST_CLIPS),'ground_planes':planes,
              'clips':num_anims,'frames':num_frames,'elements':num_elements,'catalog':catalog,'sources':sources}
    (out/'build-report.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(BANK,num_anims,'clips',num_frames,'frames',len(payload),'bytes',flush=True)


def patch_hat_offset(source_zip,out_zip,offset=HAT_LOCAL_Y_OFFSET):
    """Apply worn swap_hat local-Y offset directly to an existing wili_body_fit.zip."""
    source_zip=Path(source_zip);out_zip=Path(out_zip)
    with ZipFile(source_zip) as z:raw=z.read('anim.bin')
    bank=rig.parse_anim(raw)
    names=bank['names']
    patched=0;skipped_ground=0
    for clip in bank['anims']:
        for frame in clip['frames']:
            for e in frame['elements']:
                sym=names[e['symbol']].lower()
                if sym!='swap_hat':continue
                if e['frame'] in (0,1,2):
                    store(e,basis(e),xy(e)+hat_offset(e,sym,offset))
                    patched+=1
                else:
                    skipped_ground+=1
    payload=serialize(bank['anims'],names)
    out_zip.parent.mkdir(parents=True,exist_ok=True)
    tmp=out_zip.with_suffix(out_zip.suffix+'.tmp')
    with ZipFile(tmp,'w',ZIP_DEFLATED) as z:z.writestr('anim.bin',payload)
    tmp.replace(out_zip)
    return {
        'clips':len(bank['anims']),
        'frames':sum(len(c['frames']) for c in bank['anims']),
        'patched_swap_hat':patched,
        'skipped_non_worn_swap_hat':skipped_ground,
        'anim_bin_bytes':len(payload),
        'anim_bin_sha256':hashlib.sha256(payload).hexdigest(),
        'zip_sha256':hashlib.sha256(out_zip.read_bytes()).hexdigest(),
    }


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'art/.work/body-scale-fit/build')
    parser.add_argument('--patch-hat-from',type=Path,default=None,
                        help='Patch an existing wili_body_fit.zip with --hat-offset instead of rebuilding from DST.')
    parser.add_argument('--hat-offset',type=float,default=HAT_LOCAL_Y_OFFSET)
    args=parser.parse_args()
    if args.patch_hat_from is not None:
        target=args.out if args.out.suffix=='.zip' else args.out/(BANK+'.zip')
        report=patch_hat_offset(args.patch_hat_from,target,args.hat_offset)
        print(json.dumps(report,indent=2),flush=True)
    else:
        build(args.out)
