"""Fortnite Chest Radar (experimental): screen pixels + public third-party map APIs.
No game memory/process interaction or anti-cheat bypass. Windows / Python 3.10+.
"""
import queue
import csv
import json
import math
import os
import threading
import time
import tkinter as tk
import sys
from pathlib import Path
from tkinter import messagebox

import cv2
import mss
import numpy as np
import requests
from PIL import Image, ImageTk
from matching import Matcher
from radar_ui import RadarUI
from heading import HeadingDetector
from session_guard import SessionGuard,WindowsHUDReader
from app_paths import app_root

ROOT = app_root()
CACHE = ROOT / 'cache'
CACHE.mkdir(exist_ok=True)
CONFIG = ROOT / 'config.json'
if __name__=='__main__':
    if '--configure' in sys.argv:
        from calibra import main
        main();raise SystemExit(0)
    if '--compare-xfeat' in sys.argv:
        from compare_xfeat import main
        main();raise SystemExit(0)
    if '--self-test' in sys.argv:
        from self_test import main
        main();raise SystemExit(0)
    def startup_error(exc_type,value,tb):
        import traceback
        (ROOT/'startup_error.log').write_text(''.join(traceback.format_exception(exc_type,value,tb)),encoding='utf-8')
        try:
            window=tk.Tk();window.withdraw()
            messagebox.showerror('Chest Radar',str(value)+'\nDettagli in startup_error.log',parent=window)
            window.destroy()
        except Exception:pass
    sys.excepthook=startup_error
DEFAULT = {
    'minimap_bbox_1920': [1690, 27, 1892, 230],
    'api_key': '',
    'opacity': 0.94,
    'topmost': True,
    'chest_radius_pixels': 110,
    'matching_every_seconds': 2.5,
}

def config_load():
    c = DEFAULT.copy()
    if CONFIG.exists():
        try: c.update(json.loads(CONFIG.read_text(encoding='utf-8')))
        except Exception as exc: raise ValueError('config.json non valido: '+str(exc)) from exc
    from diagnostics import validate_config
    validate_config(c)
    return c

CFG = config_load()

def get_json(url, headers=None):
    r = requests.get(url, headers=headers or {}, timeout=18)
    r.raise_for_status()
    return r.json()

def fetch_map(ignore_local=False):
    """Download current clean map from fortnite-api.com, cache its URL per run."""
    if CFG.get('map_file') and not ignore_local:
        im=cv2.imread(str(ROOT/CFG['map_file']))
        if im is None: raise ValueError('map_file non leggibile: '+str(CFG['map_file']))
        return im, {'source':'local'}
    data = get_json('https://fortnite-api.com/v1/map')['data']
    map_url = data['images']['blank']
    r = requests.get(map_url, timeout=40)
    r.raise_for_status()
    im = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    if im is None: raise ValueError('Immagine mappa non valida')
    (CACHE / 'island_map.png').write_bytes(r.content)
    (CACHE / 'map_info.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    return im, data

def load_cached_map():
    p = CACHE / 'island_map.png'
    im = cv2.imread(str(p)) if p.exists() else None
    return im

def fetch_chests(api_key):
    """Optional data; endpoint may require paid access. Schema is not guaranteed."""
    if not api_key.strip():
        return [], 'Per le casse API inserisci api_key in config.json (se hai accesso).'
    try:
        payload = get_json('https://prod.api-fortnite.com/api/v2/map/objects/chests',
                           {'x-api-key': api_key.strip()})
        (CACHE / 'chests_raw.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        return extract_chests(payload), 'Endpoint casse interrogato.'
    except Exception as exc:
        return [], f'API casse non disponibile: {type(exc).__name__}: {exc}'

def extract_chests(payload):
    """Extract raw world coordinates only; plotting needs authoritative transform."""
    out = []
    items = payload.get('data', payload) if isinstance(payload, dict) else payload
    if isinstance(items, dict):
        for field in ('chests', 'items', 'objects', 'results'):
            if isinstance(items.get(field), list): items = items[field]; break
    if not isinstance(items, list): return out
    for x in items:
        if not isinstance(x, dict): continue
        pt = x.get('location', x.get('position', x.get('coordinates', x)))
        if isinstance(pt, dict) and 'x' in pt and 'y' in pt:
            try: out.append((float(pt['x']), float(pt['y'])))
            except (ValueError, TypeError): pass
    return out

def load_pixel_chests():
    """Allow verified user-supplied map image pixel coordinates; no fake locations."""
    p = ROOT / 'chests_pixels.csv'
    if not p.exists(): return []
    out = []
    with p.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            try: out.append((float(row['x']), float(row['y'])))
            except (KeyError, ValueError, TypeError): continue
    return out

class App(RadarUI):
    def __init__(self, root):
        self.root=root
        self.events=queue.Queue()
        self.generation=0
        self.download_busy=False
        self.latest_capture=None
        self.heading_detector=HeadingDetector(CFG.get('player_anchor',[.5,.5]))
        self.heading_busy=False;self.last_heading_attempt=0
        self.orientation_matrix=None;self.pose_revision=0
        self.heading_report={}
        self.guard=SessionGuard();self.radar_paused=False
        self.hud_reader=WindowsHUDReader(CACHE)
        self.hud_busy=False;self.hud_disabled=False;self.last_hud_attempt=0
        self.last_hud_frame=None
        self.status=tk.StringVar(value='Caricamento della mappa...')
        self.info=tk.StringVar(value='Posizione non disponibile')
        self.build_ui(CFG)
        self.big=None;self.matcher=None;self.pos=None;self.manual=False
        self.pixel_chests=load_pixel_chests()
        self.chest_source='CSV'
        self.world_chests=[]
        self.last_match=0
        self.lock=threading.Lock()
        self.match_busy=False
        self.screen=mss.mss()
        cached=load_cached_map() if not CFG.get('map_file') else None
        if cached is not None: self.use_map(cached)
        self.start_download()
        self.root.after(150,self.tick)
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def start_download(self):
        if self.download_busy: return
        self.download_busy=True
        self.status.set('Scaricamento della mappa attuale tramite API...')
        def task():
            try:
                im,_ = fetch_map()
                self.post( lambda:self.use_map(im))
            except Exception as exc:
                self.post(lambda msg=str(exc):self.status.set('Download fallito; eventuale cache potrebbe essere vecchia: '+msg))
            self.download_busy=False
            key=str(CFG.get('api_key',''))
            if key:
                chests, msg=fetch_chests(key)
                self.world_chests=chests
                self.post(lambda:self.info.set(msg+' Coordinate mondiali non mappate: serve trasformazione verificata.'))
        threading.Thread(target=task,daemon=True).start()

    def use_map(self, im):
        self.generation+=1
        self.guard.samples=[];self.guard.epoch+=1
        generation=self.generation
        self.pos=None
        self.orientation_matrix=None;self.heading=None;self.pose_revision+=1
        from motion import Motion
        self.motion=Motion()
        self.big=im
        self.rgb_map=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB))
        self.last_view_pos=None
        self.pixel_chests=load_pixel_chests()
        self.chest_source='CSV'
        if CFG.get('map_file'):
            from fortnitegg import associated_chests
            try:
                points=associated_chests(ROOT/CFG['map_file'],im)
                if points is not None:
                    self.pixel_chests=points
                    self.chest_source='Fortnite.GG'
            except Exception as exc:
                self.pixel_chests=[]
                self.info.set('Casse non caricate: '+str(exc))
        self.matcher=None
        self.status.set(f'Mappa caricata ({im.shape[1]}x{im.shape[0]}). Indicizzazione in corso...')
        def task():
            try:
                matcher=Matcher(im,CFG)
                self.post(lambda:self.set_matcher(matcher,generation))
            except Exception as exc:
                self.post(lambda msg=str(exc):self.status.set('Errore riconoscimento: '+msg))
        threading.Thread(target=task,daemon=True).start()
        self.draw()

    def minimap(self):
        index=CFG.get('monitor_index',1)
        if not 1 <= index < len(self.screen.monitors): raise ValueError('monitor_index non disponibile')
        m=self.screen.monitors[index]
        sx,sy=m['width']/1920,m['height']/1080
        l,t,r,b=CFG['minimap_bbox_1920']
        if CFG.get('minimap_bbox_pixels') is not None:
            l,t,r,b=CFG['minimap_bbox_pixels']; sx=sy=1
        if l<0 or t<0 or r*sx>m['width'] or b*sy>m['height']: raise ValueError('Ritaglio fuori dal monitor selezionato')
        box={'left':m['left']+round(l*sx),'top':m['top']+round(t*sy),
             'width':round(r*sx)-round(l*sx),'height':round(b*sy)-round(t*sy)}
        if self.root.state()!='withdrawn':
            wx,wy=self.root.winfo_x(),self.root.winfo_y()
            ww,wh=self.root.winfo_width(),self.root.winfo_height()
            if wx<box['left']+box['width'] and wx+ww>box['left'] and wy<box['top']+box['height'] and wy+wh>box['top']:
                raise ValueError('Il pannello copre la minimappa: spostalo (F9 in overlay).')
        img=np.asarray(self.screen.grab(box))
        return cv2.cvtColor(img,cv2.COLOR_BGRA2BGR)

    def tick(self):
        while not self.events.empty():
            self.events.get_nowait()()
        screen=None
        now=time.monotonic()
        # Never OCR another foreground app (e.g. this chat discussing prelobby messages).
        hud_visible=not self.native.available or self.native.game_foreground()
        if hud_visible and not self.hud_busy and not self.hud_disabled and now-self.last_hud_attempt>2:
            self.last_hud_attempt=now
            try:
                m=self.screen.monitors[CFG.get('monitor_index',1)]
                box={'left':m['left']+round(m['width']*.30),'top':m['top'],
                     'width':round(m['width']*.48),'height':round(m['height']*.26)}
                frame=cv2.cvtColor(np.asarray(self.screen.grab(box)),cv2.COLOR_BGRA2BGR)
                self.last_hud_frame=frame
                self.hud_busy=True
                threading.Thread(target=self.hud_async,args=(frame,now),daemon=True).start()
            except Exception as exc:
                self.apply_hud('',now,False,str(exc))
        permitted=not self.radar_paused and self.guard.permitted(now)
        if not hud_visible and not permitted and not self.radar_paused:
            reason='Torna a Fortnite per verificare la partita'
            if self.guard.reason!=reason:
                self.guard.reason=reason;self.draw()
        if not permitted and self.pos is not None:self.clear_tracking()
        if permitted and self.matcher and self.pos is not None and not self.manual and self.orientation_matrix is not None and not self.heading_busy and now-self.last_heading_attempt>.1:
            self.last_heading_attempt=now
            try:
                screen=self.minimap()
                self.heading_busy=True
                threading.Thread(target=self.heading_async,args=(screen,self.orientation_matrix.copy(),self.pose_revision,now),daemon=True).start()
            except Exception:
                self.heading=None
        interval=float(CFG.get('position_refresh_seconds',min(float(CFG['matching_every_seconds']),.8)))
        if permitted and self.matcher and not self.manual and not self.match_busy and now-self.last_match > interval:
            self.last_match=time.monotonic()
            self.match_busy=True
            try:
                if screen is None: screen=self.minimap()
                self.latest_capture=screen
                threading.Thread(target=self.match_async,args=(screen,self.matcher,self.guard.epoch),daemon=True).start()
            except Exception as exc:
                self.apply_error('Cattura non riuscita: '+str(exc))
                self.match_busy=False
        self.root.after(50,self.tick)

    def hud_async(self,frame,sampled_at):
        try:
            text=self.hud_reader.read(frame)
            self.post(lambda:self.apply_hud(text,sampled_at,True))
        except Exception as exc:
            self.hud_reader.close()
            self.post(lambda msg=str(exc):self.apply_hud('',sampled_at,False,msg))
        finally:self.post(lambda:setattr(self,'hud_busy',False))

    def apply_hud(self,text,sampled_at,available,error=''):
        if self.guard.last_hud_time is not None and sampled_at<self.guard.last_hud_time:return
        allowed=self.guard.update_hud(text,sampled_at,available)
        if self.radar_paused:self.guard.reason='Radar in pausa · F7 per riprendere'
        if not available:self.hud_disabled=True
        if not allowed:self.clear_tracking()
        self.draw()
        if error:self.status.set('Controllo HUD: '+error+' · F7 solo quando sei in partita')

    def clear_tracking(self):
        from motion import Motion
        self.pos=None;self.heading=None;self.orientation_matrix=None
        self.last_view_pos=None;self.motion=Motion();self.pose_revision+=1
        self.draw()

    def toggle_tracking(self):
        if (self.guard.ocr_available is False or self.guard.phase=='checking') and not self.guard.manual_confirmed:
            self.radar_paused=False
            self.guard.confirm_manually()
        else:
            self.radar_paused=not self.radar_paused
            self.guard.samples=[];self.guard.epoch+=1
            self.guard.reason='Radar in pausa · F7 per riprendere' if self.radar_paused else 'Conferma della posizione in corso'
        self.clear_tracking()

    def heading_async(self,screen,matrix,revision,sampled_at):
        try:
            angle=self.heading_detector.estimate(screen,matrix)
            report=dict(self.heading_detector.last_report)
            self.post(lambda:self.apply_heading(angle,report,revision,sampled_at))
        except Exception as exc:
            self.post(lambda msg=str(exc):self.apply_heading(None,{'reason':msg},revision,sampled_at))
        finally:
            self.post(lambda:setattr(self,'heading_busy',False))

    def apply_heading(self,angle,report,revision,sampled_at):
        if revision!=self.pose_revision or self.pos is None or self.manual:return
        if angle is not None:
            self.heading=angle
            self.heading_timestamp=sampled_at
        elif time.monotonic()-self.heading_timestamp>.35:
            self.heading=None
        self.heading_report=report

    def match_async(self,screen,matcher,epoch=None):
        try:
            result=matcher.locate(screen)
            self.post(lambda:self.apply_result(result) if matcher is self.matcher and not self.radar_paused and (epoch is None or epoch==self.guard.epoch) else None)
        except Exception as exc:
            self.post(lambda msg=str(exc):self.apply_error(msg) if matcher is self.matcher and not self.radar_paused and (epoch is None or epoch==self.guard.epoch) else None)
        finally:
            self.post(lambda:setattr(self,'match_busy',False))

    def apply_result(self,result):
        if self.manual: return
        if result:
            x,y,n=result
            if not self.guard.candidate((x,y),self.matcher.last_report,time.monotonic()):
                self.clear_tracking()
                self.status.set(self.guard.reason)
                return
            self.pos=(x,y)
            self.last_view_pos=self.pos
            self.last_position_time=time.monotonic()
            matrix=self.matcher.last_report.get('map_transform')
            self.orientation_matrix=np.asarray(matrix,dtype=float) if matrix is not None else None
            self.pose_revision+=1
            self.status.set('Stima accettata geometricamente; verificare nel gioco.')
            self.info.set(f'POSIZIONE STIMATA: pixel ({x:.0f}, {y:.0f}) | {n} corrispondenze. NON verificata; controlla sulla mappa!')
            self.draw()
        else:
            self.guard.failed()
            self.clear_tracking()
            self.status.set(self.matcher.last_report.get('reason','Matching rifiutato'))
            self.info.set('Nessuna corrispondenza affidabile. Indicatore precedente rimosso. Salva diagnostica o usa Posizione manuale.')

    def toggle_manual(self):
        self.manual=not self.manual
        self.pos=None
        self.heading=None;self.orientation_matrix=None;self.pose_revision+=1
        self.draw()
        self.status.set('MANUALE: clicca sulla mappa per impostare la posizione.' if self.manual else 'AUTOMATICO: tentativi di matching dalla minimappa.')

    def on_map_click(self,event):
        if not self.manual or self.big is None or self.view is None: return
        if self.overlay_mode and self.overlay_locked: return
        ox,oy=self.map_offset
        if not (0<=event.x-ox<self.view.size and 0<=event.y-oy<self.view.size): return
        x,y=self.view.map_point(event.x-ox,event.y-oy)
        h,w=self.big.shape[:2]
        self.pos=(max(0,min(w-1,x)),max(0,min(h-1,y)))
        self.last_view_pos=self.pos
        self.info.set('Posizione impostata manualmente')
        self.draw()

    def reload_chests(self):
        self.pixel_chests=load_pixel_chests()
        self.chest_source='CSV'
        self.status.set(f'Caricate {len(self.pixel_chests)} casse da chests_pixels.csv (coordinate pixel mappa).')
        self.draw()

    def start_gg(self):
        if self.download_busy: return
        self.download_busy=True
        self.status.set('Caricamento mappa e casse da Fortnite.GG...')
        def task():
            try:
                from fortnitegg import download, align_to_reference
                im,data,filename=download(CACHE,lambda msg:self.post(lambda text=msg:self.status.set(text)))
                self.post(lambda:self.status.set('Allineamento casse GG sulla mappa API compatibile con il gioco...'))
                reference,_=fetch_map(ignore_local=True)
                im,data,filename=align_to_reference(im,reference,data,CACHE)
                self.post(lambda:self.finish_gg(im,data,filename))
            except Exception as exc:
                self.post(lambda msg=str(exc):self.status.set('Importazione Fortnite.GG fallita: '+msg))
            finally:
                self.post(lambda:setattr(self,'download_busy',False))
        threading.Thread(target=task,daemon=True).start()

    def finish_gg(self, im, data, filename):
        CFG['map_file']=str(filename.relative_to(ROOT))
        CONFIG.write_text(json.dumps(CFG,indent=2),encoding='utf-8')
        self.use_map(im)
        self.info.set(f"Caricate {len(data['points'])} casse Fortnite.GG. Punti gialli = casse segnalate nelle vicinanze.")

    def restore_api(self):
        if self.download_busy: return
        CFG.pop('map_file',None)
        CONFIG.write_text(json.dumps(CFG,indent=2),encoding='utf-8')
        self.start_download()

    def post(self, callback):
        self.events.put(callback)

    def set_matcher(self, matcher, generation):
        if generation != self.generation: return
        self.matcher=matcher
        self.status.set('Pronto. Mappa e modalita devono corrispondere al gioco; stime non verificate.')

    def apply_error(self, msg):
        self.pos=None
        self.heading=None;self.orientation_matrix=None;self.pose_revision+=1
        self.draw()
        self.status.set(msg)

    def configure_minimap(self):
        import subprocess
        args=[sys.executable,'--configure'] if getattr(sys,'frozen',False) else [sys.executable,str(ROOT/'radar.py'),'--configure']
        subprocess.Popen(args,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.notify('Configurazione aperta. Dopo aver salvato, riavvia il radar.')

    def compare_xfeat(self):
        if self.latest_capture is None or self.big is None or self.matcher is None:
            self.notify('Serve prima una cattura della minimappa e la mappa caricata.');return
        if self.match_busy or getattr(self,'xfeat_busy',False):
            self.notify('Attendi la fine del riconoscimento.');return
        # Independent matchers and copied inputs: never mutate the live pose or its report.
        self.xfeat_busy=True
        image=self.big.copy();crop=self.latest_capture.copy();config=dict(CFG)
        self.notify('Confronto offline XFeat in corso; posizione live invariata.')
        def task():
            try:
                from compare_xfeat import compare,save_report
                result=compare(image,crop,__import__('app_paths').resource_path('models/xfeat.onnx'),config)
                target=save_report(result,ROOT/'diagnostics')
                a=result['SIFT'];b=result['XFeat']
                text=f"SIFT {a['median_ms']:.0f} ms / XFeat {b['median_ms']:.0f} ms. XFeat: {'stima' if b['position'] else 'nessuna stima'}."
                self.post(lambda:self.show_comparison(text,target))
            except Exception as exc:
                self.post(lambda msg=str(exc):self.notify('Confronto non disponibile: '+msg))
            finally:self.post(lambda:setattr(self,'xfeat_busy',False))
        threading.Thread(target=task,daemon=True).start()

    def show_comparison(self,text,target):
        self.notify(text)
        messagebox.showinfo('Confronto locale sperimentale',text+'\n\nReport: '+str(target)+'\nNessun riferimento reale: queste misure non dimostrano maggiore precisione. Nessun cambiamento alla posizione live.',parent=self.root)

    def save_diagnostics(self):
        if self.match_busy:
            self.status.set('Matching in corso: riprova tra pochi secondi.')
            return
        from diagnostics import save_bundle
        if self.latest_capture is None:
            try:self.latest_capture=self.minimap()
            except Exception as exc:
                self.status.set('Cattura diagnostica non disponibile: '+str(exc));return
        folder=save_bundle(ROOT/'diagnostics',self.latest_capture,self.matcher)
        safe={k:CFG.get(k) for k in ('monitor_index','minimap_bbox_1920','minimap_bbox_pixels','player_anchor','excluded_rects','map_file')}
        (folder/'capture_config.json').write_text(json.dumps(safe,indent=2),encoding='utf-8')
        (folder/'heading_report.json').write_text(json.dumps(self.heading_report,indent=2),encoding='utf-8')
        phase={'phase':self.guard.phase,'reason':self.guard.reason,'ocr_available':self.guard.ocr_available,
               'confirmed_samples':len(self.guard.samples),'manual_confirmation':self.guard.manual_confirmed,'paused':self.radar_paused}
        (folder/'phase_report.json').write_text(json.dumps(phase,indent=2),encoding='utf-8')
        if self.last_hud_frame is not None:cv2.imwrite(str(folder/'hud_phase.png'),self.last_hud_frame)
        self.status.set('Diagnostica salvata in '+str(folder))

    def close(self):
        self.native.close()
        self.hud_reader.close()
        try:self.screen.close()
        except Exception:pass
        self.root.destroy()

if __name__=='__main__':
    import sys
    if '--overlay' in sys.argv: CFG['overlay_on_start']=True
    if os.name=='nt':
        import ctypes
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception: pass
    from single_instance import acquire
    if not acquire(ROOT):
        window=tk.Tk();window.withdraw()
        messagebox.showinfo('Chest Radar','Il radar è già aperto. F8 mostra il pannello; F10 mostra o nasconde l’overlay.',parent=window)
        window.destroy();raise SystemExit(0)
    root=tk.Tk()
    App(root)
    root.mainloop()
