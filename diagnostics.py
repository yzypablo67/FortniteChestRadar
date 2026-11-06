"""Offline replay and shareable diagnostics; never writes API keys."""
import argparse
import json
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from matching import Matcher


def validate_config(c):
    for name,default,low,high in (('overlay_opacity',.92,.3,1),('view_span_pixels',220,120,1400),('position_refresh_seconds',.8,.25,30)):
        value=c.get(name,default)
        if type(value) not in (int,float) or not np.isfinite(value) or not low<=value<=high:
            raise ValueError(f'{name}: valore tra {low} e {high}')
    if type(c.get('overlay_on_start',False)) is not bool:
        raise ValueError('overlay_on_start deve essere true oppure false')
    for name in ('minimap_bbox_1920','minimap_bbox_pixels'):
        v=c.get(name)
        if v is None and name.endswith('pixels'): continue
        if not isinstance(v,list) or len(v)!=4 or not all(isinstance(x,(int,float)) and np.isfinite(x) for x in v) or not (0<=v[0]<v[2] and 0<=v[1]<v[3]):
            raise ValueError(name+': usare [sinistra, alto, destra, basso] validi')
    anchor=c.get('player_anchor',[.5,.5])
    if not isinstance(anchor,list) or len(anchor)!=2 or not all(isinstance(v,(int,float)) and 0<=v<=1 for v in anchor):
        raise ValueError('player_anchor deve contenere due frazioni tra 0 e 1')
    if type(c.get('monitor_index',1)) is not int or c.get('monitor_index',1)<1:
        raise ValueError('monitor_index deve essere un intero positivo')
    if not isinstance(c.get('matching_every_seconds',2.5),(int,float)) or not np.isfinite(c.get('matching_every_seconds',2.5)) or c.get('matching_every_seconds',2.5)<=0:
        raise ValueError('matching_every_seconds deve essere positivo e finito')
    for rect in c.get('excluded_rects',[]):
        if len(rect)!=4 or not all(isinstance(v,(int,float)) and 0<=v<=1 for v in rect) or not (rect[0]<rect[2] and rect[1]<rect[3]):
            raise ValueError('excluded_rects: rettangoli in frazioni tra 0 e 1')


def save_bundle(base, crop, matcher):
    folder=Path(base)/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True)
    cv2.imwrite(str(folder/'minimap.png'),crop)
    report={'accepted':False,'reason':'Matcher non pronto'}
    if matcher is not None:
        report=matcher.last_report
        cv2.imwrite(str(folder/'reference.png'),matcher.big)
        if matcher.last_visual is not None: cv2.imwrite(str(folder/'matches.png'),matcher.last_visual)
    report=dict(report,opencv=cv2.__version__,numpy=np.__version__)
    (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return folder


def main():
    parser=argparse.ArgumentParser(description='Riproduci matching senza gioco o rete')
    parser.add_argument('--map',required=True)
    parser.add_argument('--minimap',required=True)
    parser.add_argument('--config',default='config.json')
    parser.add_argument('--out',default='diagnostics')
    a=parser.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig')); validate_config(cfg)
    big=cv2.imread(a.map); small=cv2.imread(a.minimap)
    if big is None or small is None: parser.error('Mappa o minimappa non leggibile')
    matcher=Matcher(big,cfg); result=matcher.locate(small)
    folder=save_bundle(a.out,small,matcher)
    print(json.dumps({'result':result,'reason':matcher.last_report['reason'],'diagnostics':str(folder)},ensure_ascii=False))
    return 0 if result else 2


if __name__=='__main__':
    raise SystemExit(main())
