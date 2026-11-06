"""HUD phase filtering and temporal confirmation. Unknown OCR never silently enables tracking."""
import json
import math
import os
import queue
import re
import subprocess
import threading
import unicodedata
import uuid
from pathlib import Path
import cv2


def blocked_phase(text):
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().upper()
    text=re.sub(r'[^A-Z0-9 ]',' ',text);text=' '.join(text.split())
    if ('ATTESA' in text and 'GIOCATOR' in text) or 'WAITING FOR PLAYERS' in text:return 'prelobby'
    if ('BUS' in text and any(word in text for word in ('PARTENZA','PARTE TRA','PARTIRA','DECOLL','LAUNCH'))):return 'prelobby'
    if any(word in text for word in ('TORNA ALLA LOBBY','RETURN TO LOBBY','SEI STATO ELIMINATO','YOU PLACED','SPETTATORE','SPECTATING')):return 'fuori partita'
    return None


class SessionGuard:
    def __init__(self):
        self.phase='checking';self.ocr_available=None;self.last_hud_time=None
        self.clear_reads=0;self.samples=[];self.manual_confirmed=False;self.failures=0
        self.epoch=0;self.reason='Controllo della partita in corso'

    def update_hud(self,text,now,available=True):
        phase=blocked_phase(text) if available else None
        self.ocr_available=available;self.last_hud_time=now
        if not available:
            self.phase='unavailable';self.samples=[];self.epoch+=1
            self.reason='Controllo HUD non disponibile · F7 conferma in partita'
            return False
        if phase:
            self.phase=phase;self.clear_reads=0;self.samples=[]
            self.manual_confirmed=False;self.epoch+=1
            self.reason='Prelobby · radar in pausa' if phase=='prelobby' else 'Fuori partita · radar in pausa'
            return False
        if self.phase=='checking' and not text.strip():
            if not self.manual_confirmed:self.reason='Fase non leggibile · F7 solo quando sei in partita'
            return self.manual_confirmed
        self.clear_reads+=1
        if self.phase in ('prelobby','fuori partita') and self.clear_reads<2:return False
        if self.phase!='ready':self.samples=[];self.epoch+=1
        self.phase='ready';self.reason='Conferma della posizione in corso'
        return True

    def confirm_manually(self):
        if self.phase in ('prelobby','fuori partita'):return False
        self.manual_confirmed=True;self.samples=[];self.epoch+=1;self.reason='Conferma della posizione in corso'
        return True

    def permitted(self,now):
        if self.phase in ('prelobby','fuori partita'):return False
        fresh=self.last_hud_time is not None and now-self.last_hud_time<=7
        return (self.phase=='ready' and fresh) or self.manual_confirmed

    def candidate(self,position,report,now):
        self.failures=0
        if self.phase in ('prelobby','fuori partita'):return False
        fresh=self.last_hud_time is not None and now-self.last_hud_time<=7
        if not self.permitted(now):
            self.samples=[]
            if not fresh and self.ocr_available:self.reason='Controllo HUD in ritardo · radar in pausa'
            return False
        best=report.get('best',{})
        if best.get('inliers',0)<20 or best.get('inlier_ratio',0)<.6 or best.get('coverage',0)<.16:
            self.samples=[];self.reason='Allineamento troppo debole per mostrare una posizione'
            return False
        if self.samples:
            previous,when=self.samples[-1]
            if 0<now-when<.15:
                self.reason='Attesa della prossima lettura indipendente'
                return False
            if now<=when or now-when>3 or math.dist(previous,position)>max(25,100*(now-when)):
                self.samples=[]
        self.samples.append((tuple(position),now));self.samples=self.samples[-3:]
        if len(self.samples)<3:
            self.reason=f'Conferma posizione {len(self.samples)}/3'
            return False
        self.reason='Posizione confermata su 3 letture'
        return True

    def failed(self):
        self.samples=[];self.failures+=1
        if self.phase=='ready':self.reason='Posizione non confermata · ricerca in corso'
        if self.failures>=3:
            self.manual_confirmed=False
            if self.ocr_available is False:self.reason='Posizione persa · F7 conferma in partita'


class WindowsHUDReader:
    def __init__(self,folder):
        self.folder=Path(folder);self.folder.mkdir(exist_ok=True)
        self.process=None;self.replies=queue.Queue()
        self.pending_files=[]

    def start(self):
        if os.name!='nt':raise OSError('OCR HUD disponibile su Windows')
        script=Path(__file__).with_name('windows_ocr.ps1').read_text(encoding='utf-8')
        self.process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        process=self.process
        def read_lines():
            for line in process.stdout:
                try:self.replies.put(json.loads(line))
                except ValueError:continue
            self.replies.put({'ok':False,'error':'Motore OCR Windows non disponibile'})
        threading.Thread(target=read_lines,daemon=True,name='hud-ocr-output').start()

    def read(self,frame):
        if self.process is None:self.start()
        self.clean_files()
        path=(self.folder/('_hud_'+uuid.uuid4().hex+'.png')).resolve()
        self.pending_files.append(path)
        if not cv2.imwrite(str(path),frame):raise OSError('Salvataggio HUD fallito')
        self.process.stdin.write(json.dumps({'path':str(path)})+'\n');self.process.stdin.flush()
        try:reply=self.replies.get(timeout=5)
        except queue.Empty:
            self.close();raise TimeoutError('OCR HUD non risponde')
        if not reply.get('ok'):raise OSError(reply.get('error','OCR non disponibile'))
        return reply.get('text','')

    def clean_files(self):
        remaining=[]
        for path in self.pending_files:
            try:path.unlink(missing_ok=True)
            except OSError:remaining.append(path)
        self.pending_files=remaining

    def close(self):
        if self.process is not None:
            try:self.process.kill()
            except OSError:pass
            try:self.process.wait(timeout=1)
            except (OSError,subprocess.TimeoutExpired):pass
            self.process=None
        self.clean_files()
