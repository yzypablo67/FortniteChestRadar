"""Graphical minimap calibration for Python and the portable EXE."""
import json,os,tkinter as tk
from tkinter import messagebox
import cv2,mss,numpy as np
from app_paths import app_root


def main():
    if os.name=='nt':
        import ctypes
        try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:pass
    path=app_root()/'config.json'
    try:config=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    except (ValueError,OSError):
        error=tk.Tk();error.withdraw();messagebox.showerror('Configurazione','config.json non leggibile. Conservane una copia prima di correggerlo.');error.destroy();return
    with mss.mss() as screen:monitors=screen.monitors[1:]
    root=tk.Tk();root.title('Configura la minimappa');root.geometry('620x330');root.configure(bg='#101419')
    tk.Label(root,text='La tua minimappa, al pixel giusto.',font=('Segoe UI',17,'bold'),bg='#101419',fg='#f4f0e7').pack(anchor='w',padx=24,pady=(24,12))
    choices=[f"Monitor {i} · {m['width']} × {m['height']}" for i,m in enumerate(monitors,1)]
    if not choices:messagebox.showerror('Monitor','Nessun monitor disponibile.',parent=root);root.destroy();return
    index=min(max(0,config.get('monitor_index',1)-1),len(choices)-1)
    selected=tk.StringVar(value=choices[index]);tk.OptionMenu(root,selected,*choices).pack(anchor='w',padx=24)
    tk.Label(root,text='Apri Fortnite con la minimappa visibile. Premi il pulsante e torna al gioco.\nDopo 3 secondi seleziona SOLO il quadrato della minimappa.\nInvio conferma; C oppure Esc annulla. Il giocatore deve essere al centro.',
             justify='left',font=('Segoe UI',10),bg='#101419',fg='#a4adb8').pack(anchor='w',padx=24,pady=16)
    def capture():
        try:
            chosen=choices.index(selected.get())+1
            with mss.mss() as screen:
                if chosen>=len(screen.monitors):raise ValueError('Monitor scollegato: riapri la configurazione.')
                image=cv2.cvtColor(np.asarray(screen.grab(screen.monitors[chosen])),cv2.COLOR_BGRA2BGR)
            scale=min(1.,1400/image.shape[1],850/image.shape[0])
            preview=cv2.resize(image,None,fx=scale,fy=scale)
            x,y,w,h=cv2.selectROI('Solo minimappa - Invio conferma - C annulla',preview,showCrosshair=True)
            cv2.destroyAllWindows();root.deiconify()
            if not w or not h:return
            if w/scale<48 or h/scale<48:raise ValueError('Ritaglio troppo piccolo: seleziona almeno 48 × 48 pixel.')
            config['monitor_index']=chosen
            config['minimap_bbox_pixels']=[round(x/scale),round(y/scale),round((x+w)/scale),round((y+h)/scale)]
            temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(config,indent=2),encoding='utf-8');temporary.replace(path)
            messagebox.showinfo('Salvato','Minimappa configurata. Chiudi e riapri Chest Radar.',parent=root)
            root.destroy()
        except Exception as exc:
            cv2.destroyAllWindows();root.deiconify();messagebox.showerror('Configurazione',str(exc),parent=root)
    def start():root.withdraw();root.after(3000,capture)
    tk.Button(root,text='Seleziona minimappa fra 3 secondi',command=start,bg='#84dfcd',fg='#101419',relief='flat',font=('Segoe UI',11,'bold'),padx=12,pady=10).pack(anchor='w',padx=24)
    root.mainloop()

if __name__=='__main__':main()
