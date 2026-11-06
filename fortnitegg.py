"""Public Fortnite.GG map + spawn importer, without executing remote JavaScript."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit
import cv2
import numpy as np
import requests

BASE='https://fortnite.gg/'

def fingerprint(image):
    return hashlib.sha256(image.tobytes()).hexdigest()

def parse_spawns(text):
    # Strict data assignment, never eval/exec website code.
    match=re.fullmatch(r'\s*window\.Spawns\s*=\s*(\{.*\})\s*;?\s*',text,re.S)
    if not match: raise ValueError('Formato dati Fortnite.GG cambiato')
    data=json.loads(match.group(1))
    groups=data.get('chests')
    if not isinstance(groups,list) or not groups: raise ValueError('Dati casse mancanti')
    points=[]
    for group in groups:
        for point in group.get('coords',[]):
            if not isinstance(point,list) or len(point)!=2:
                raise ValueError('Coordinate casse non riconosciute')
            lat,lng=point
            if not all(type(v) in (int,float) and np.isfinite(v) for v in point) or not (-256<=lat<=0 and 0<=lng<=256):
                raise ValueError('Coordinate casse fuori mappa')
            points.append((float(lng)/256, -float(lat)/256))
    if not points: raise ValueError('Elenco casse vuoto')
    return sorted(set(points))

def public_script(html,stem):
    sources=re.findall(r'<script\b[^>]*\bsrc=["\x27]([^"\x27]+)',html,re.I)
    for source in sources:
        url=urljoin(BASE,source)
        parts=urlsplit(url)
        if parts.scheme=='https' and parts.netloc=='fortnite.gg' and parts.path==f'/data/{stem}.js': return url
    raise ValueError('Script dati non trovato: '+stem)

def get(url):
    response=requests.get(url,timeout=30)
    response.raise_for_status()
    return response

def download(destination,progress=lambda message:None):
    html=get(BASE).text
    data_url=public_script(html,'en')
    spawn_url=public_script(html,'spawns')
    # Read only metadata from the language script, which also contains non-JSON references.
    metadata=get(data_url).text
    m=re.search(r'"map"\s*:\s*"([A-Za-z0-9_-]+)"',metadata)
    if not m: raise ValueError('Identificativo mappa Fortnite.GG mancante')
    map_id=m.group(1)
    spawns=get(spawn_url).text
    points=parse_spawns(spawns)
    progress(f'Scaricamento mappa Fortnite.GG: {len(points)} casse...')
    # Leaflet CRS.Simple bounds [-256,0]..[0,256], native zoom 3: 8x8 tiles.
    mosaic=np.empty((2048,2048,3),np.uint8)
    def tile(position):
        x,y=position
        url=f'{BASE}maps/{map_id}/3/{x}/{y}.webp'
        image=cv2.imdecode(np.frombuffer(get(url).content,np.uint8),cv2.IMREAD_COLOR)
        if image is None or image.shape!=(256,256,3): raise ValueError('Tassello mappa non valido')
        return x,y,image
    with ThreadPoolExecutor(max_workers=4) as pool:
        for x,y,image in pool.map(tile,[(x,y) for y in range(8) for x in range(8)]):
            mosaic[y*256:(y+1)*256,x*256:(x+1)*256]=image
    # Detect a map rollover during download instead of silently combining versions.
    if get(data_url).text != metadata or get(spawn_url).text != spawns:
        raise ValueError('Dati aggiornati durante il download: riprovare')
    import uuid
    folder=Path(destination)/('gg_'+uuid.uuid4().hex[:12]); folder.mkdir(parents=True)
    filename=folder/'map.png'
    if not cv2.imwrite(str(filename),mosaic): raise OSError('Impossibile salvare la mappa')
    payload={'source':BASE,'map_id':map_id,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
             'map_sha256':fingerprint(mosaic),'map_size':[2048,2048],
             'points':[[x*2048,y*2048] for x,y in points],
             'meaning':'Punti di spawn delle casse standard, non stato live della partita'}
    (folder/'chests.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    return mosaic,payload,filename

def associated_chests(filename,image):
    path=Path(filename).with_name('chests.json')
    if not path.exists(): return None
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('map_sha256')!=fingerprint(image): raise ValueError('Casse Fortnite.GG non associate a questa mappa')
    h,w=image.shape[:2]
    points=data.get('points',[])
    if not points or not all(isinstance(p,list) and len(p)==2 and all(type(v) in (int,float) and np.isfinite(v) for v in p) and 0<=p[0]<=w and 0<=p[1]<=h for p in points):
        raise ValueError('Dataset casse Fortnite.GG non valido')
    return [tuple(p) for p in points]

def align_to_reference(source, reference, data, destination):
    """Keep the game-compatible reference; geometrically register GG spawn coordinates."""
    detector=cv2.SIFT_create(nfeatures=35000,contrastThreshold=.012)
    sk,sd=detector.detectAndCompute(cv2.cvtColor(source,cv2.COLOR_BGR2GRAY),None)
    rk,rd=detector.detectAndCompute(cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY),None)
    if sd is None or rd is None or len(rd)<2: raise ValueError('Mappe senza dettagli per allineamento casse')
    pairs=cv2.BFMatcher().knnMatch(sd,rd,k=2)
    solutions=[]
    for ratio in (.8,.85):
        matches=[p[0] for p in pairs if len(p)==2 and p[0].distance<ratio*p[1].distance]
        unique={}
        for match in sorted(matches,key=lambda m:m.distance): unique.setdefault(match.trainIdx,match)
        matches=list(unique.values())
        if len(matches)<25: raise ValueError('Mappe GG/API non allineabili: pochi punti comuni')
        src=np.float32([sk[m.queryIdx].pt for m in matches])
        dst=np.float32([rk[m.trainIdx].pt for m in matches])
        matrix,flags=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=10000,confidence=.999)
        if matrix is None: raise ValueError('Mappe GG/API non allineabili')
        valid=flags.ravel().astype(bool); count=int(valid.sum())
        coverage=cv2.contourArea(cv2.convexHull(src[valid]))/(source.shape[0]*source.shape[1])
        error=float(np.median(np.linalg.norm(cv2.transform(src[None],matrix)[0][valid]-dst[valid],axis=1)))
        if count<25 or coverage<.12 or error>1.5:
            raise ValueError(f'Allineamento casse insufficiente: {count} punti, copertura {coverage:.2f}, errore {error:.2f}px')
        solutions.append((matrix,{'inliers':count,'coverage':coverage,'median_error_pixels':error,'ratio':ratio}))
    h,w=source.shape[:2]
    corners=np.float32([[[0,0],[w,0],[w,h],[0,h]]])
    disagreement=float(np.max(np.linalg.norm(cv2.transform(corners,solutions[0][0])-cv2.transform(corners,solutions[1][0]),axis=2)))
    if disagreement>3: raise ValueError('Allineamenti casse discordanti tra soglie')
    matrix,report=solutions[-1]
    converted=cv2.transform(np.float32([data['points']]),matrix)[0]
    rh,rw=reference.shape[:2]
    if not np.all((converted[:,0]>=0)&(converted[:,0]<rw)&(converted[:,1]>=0)&(converted[:,1]<rh)):
        raise ValueError('Casse proiettate fuori dalla mappa API')
    import uuid
    folder=Path(destination)/('aligned_'+uuid.uuid4().hex[:12]); folder.mkdir(parents=True)
    filename=folder/'map.png'
    if not cv2.imwrite(str(filename),reference): raise OSError('Salvataggio mappa API fallito')
    payload=dict(data,points=converted.tolist(),map_sha256=fingerprint(reference),
                 source_map_sha256=fingerprint(source),map_size=[rw,rh],
                 alignment=dict(report,matrix=matrix.tolist(),cross_threshold_disagreement_pixels=disagreement))
    (folder/'chests.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    return reference,payload,filename

if __name__=='__main__':
    image,data,path=download(Path(__file__).resolve().parent/'cache',print)
    print(json.dumps({'map':str(path),'chests':len(data['points']),'map_id':data['map_id']}))
