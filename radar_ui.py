"""Dark desktop dashboard and compact external in-game map overlay."""
import tkinter as tk
import time
from PIL import Image,ImageTk
import cv2
from map_view import render_map,viewport,detail_span,nearby,chest_icon
from motion import Motion
from windows_overlay import WindowsOverlay

BG='#101419'; PANEL='#1b222b'; INK='#f4f0e7'; MUTED='#a4adb8'; ACCENT='#84dfcd'; GOLD='#f4c867'


class RadarUI:
    def build_ui(self,config):
        self.ui_config=config
        self.root.configure(bg=BG)
        self.root.geometry('720x870+40+65')
        self.root.minsize(640,720)
        self.root.title('Chest Radar')
        self.overlay_mode=False;self.overlay_locked=True;self.overlay_hidden=False
        self.detail_mode=True
        self.auto_zoom=True;self.view_span=float(config.get('view_span_pixels',220))
        self.last_view_pos=None;self.rgb_map=None;self.view=None;self.last_position_time=0
        self.motion=Motion();self.heading=None;self.heading_timestamp=0
        self._paint_requested=True;self._last_animation_time=time.monotonic()
        self.desktop_geometry='720x870+40+65'
        self.native=WindowsOverlay(self.root)
        self.state_text=tk.StringVar(value='IN ATTESA DELLA MINIMAPPA')
        self.count_text=tk.StringVar(value='—')
        self.mode_text=tk.StringVar(value='ZOOM AUTOMATICO')
        self.hint_text=tk.StringVar(value='F6 Zoom densità · F7 Pausa/Avvia\nF8 Overlay · F9 Sblocca · F10 Nascondi')
        self.header=tk.Frame(self.root,bg=BG);self.header.pack(fill='x',padx=20,pady=(18,12))
        title=tk.Frame(self.header,bg=BG);title.pack(fill='x')
        self.brand_icon=ImageTk.PhotoImage(chest_icon(38))
        tk.Label(title,image=self.brand_icon,bg=BG).pack(side='left',padx=(0,10))
        self.brand=tk.Label(title,text='CHEST RADAR',font=('Segoe UI',15,'bold'),fg=INK,bg=BG);self.brand.pack(side='left')
        self.live=tk.Label(title,text='●  RICERCA',font=('Segoe UI',9,'bold'),fg=GOLD,bg=BG);self.live.pack(side='right')
        tk.Label(self.header,textvariable=self.state_text,font=('Segoe UI',9),fg=MUTED,bg=BG).pack(anchor='w',pady=(7,0))
        for widget in (self.header,title,self.brand):
            widget.bind('<ButtonPress-1>',self.drag_start)
            widget.bind('<B1-Motion>',self.drag_move)
        self.metrics=tk.Frame(self.root,bg=PANEL);self.metrics.pack(fill='x',padx=20,pady=(0,10))
        tk.Label(self.metrics,textvariable=self.count_text,font=('Segoe UI',30,'bold'),fg=GOLD,bg=PANEL).pack(side='left',padx=(16,8),pady=7)
        tk.Label(self.metrics,text='PUNTI CASSA VICINI',font=('Segoe UI',9,'bold'),fg=INK,bg=PANEL).pack(side='left')
        tk.Label(self.metrics,textvariable=self.mode_text,font=('Segoe UI',8),fg=ACCENT,bg=PANEL).pack(side='right',padx=12)
        self.map_frame=tk.Frame(self.root,bg=PANEL,highlightbackground='#35404c',highlightthickness=1);self.map_frame.pack(fill='both',expand=True,padx=20)
        self.canvas=tk.Canvas(self.map_frame,width=530,height=530,bg=PANEL,highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda event:self.schedule_draw())
        self.canvas.bind('<Button-1>',self.on_map_click)
        self.canvas.bind('<MouseWheel>',lambda event:self.zoom_by(.8 if event.delta>0 else 1.25))
        self.controls=tk.Frame(self.root,bg=BG);self.controls.pack(fill='x',padx=20,pady=10)
        self.button(self.controls,'−',lambda:self.zoom_by(1.25)).pack(side='left')
        self.button(self.controls,'+',lambda:self.zoom_by(.8)).pack(side='left',padx=5)
        self.zoom_button=self.button(self.controls,'Isola intera',self.toggle_zoom);self.zoom_button.pack(side='left',padx=5)
        self.detail_button=self.button(self.controls,'Zoom ampio F6',self.toggle_detail);self.detail_button.pack(side='left',padx=5)
        self.button(self.controls,'Overlay F8',self.toggle_overlay,accent=True).pack(side='right')
        self.tools=tk.Frame(self.root,bg=BG);self.tools.pack(fill='x',padx=20,pady=(0,8))
        self.button(self.tools,'Aggiorna casse',self.start_gg,accent=True).pack(side='left')
        self.button(self.tools,'Pausa / Avvia F7',self.toggle_tracking).pack(side='left',padx=5)
        self.button(self.tools,'Manuale',self.toggle_manual).pack(side='left')
        self.settings=tk.Frame(self.root,bg=BG);self.settings.pack(fill='x',padx=20,pady=(0,8))
        self.button(self.settings,'Configura minimappa',self.configure_minimap).pack(side='left')
        self.button(self.settings,'Diagnostica',self.save_diagnostics).pack(side='left',padx=5)
        self.button(self.settings,'Confronta XFeat',self.compare_xfeat).pack(side='left')
        self.detail=tk.Label(self.root,textvariable=self.status,wraplength=590,justify='left',font=('Segoe UI',8),fg=MUTED,bg=BG)
        self.detail.pack(fill='x',padx=20,pady=(0,5))
        self.footer=tk.Label(self.root,textvariable=self.hint_text,font=('Segoe UI',8),fg=MUTED,bg=BG)
        self.footer.pack(fill='x',padx=12,pady=(0,10))
        # Reserve controls and keyboard hints before allocating remaining space to the map.
        for widget in (self.footer,self.detail,self.settings,self.tools,self.controls):
            widget.pack_configure(side='bottom',before=self.map_frame)
        self.notice=tk.Label(self.root,text='',bg=BG,fg=ACCENT,font=('Segoe UI',8),wraplength=310)
        self._notice_after=None
        self._draw_after=None;self._drag=None;self._was_game=False
        self.root.after(100,self.poll_hotkeys)
        self.root.after(33,self.animate)
        if config.get('overlay_on_start',False): self.root.after(900,self.toggle_overlay)

    def button(self,parent,text,command,accent=False):
        return tk.Button(parent,text=text,command=command,bg=ACCENT if accent else PANEL,
                         fg=BG if accent else INK,font=('Segoe UI',9,'bold'),relief='flat',
                         activebackground='#2a4057',activeforeground=INK,bd=0,padx=11,pady=8,cursor='hand2')

    def schedule_draw(self):
        if self._draw_after is not None: self.root.after_cancel(self._draw_after)
        self._draw_after=self.root.after(45,self.draw)

    def draw(self):
        self._draw_after=None
        self._paint_requested=True

    def animate(self):
        started=time.monotonic()
        dt=started-self._last_animation_time;self._last_animation_time=started
        if self.big is not None and self.rgb_map is not None and self.root.state()!='withdrawn':
            size=max(64,min(max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())))
            span=detail_span(self.view_span,self.pos,self.pixel_chests) if self.detail_mode else self.view_span
            target=viewport(self.big.shape,size,(self.pos or self.last_view_pos) if self.auto_zoom else None,span)
            heading=self.heading if self.pos is not None and started-self.heading_timestamp<.35 else None
            changed=self.motion.step(target,self.pos,heading,dt)
            if changed or self._paint_requested:
                self.paint_frame(size)
                self._paint_requested=False
        elapsed=time.monotonic()-started
        self.root.after(max(1,33-round(elapsed*1000)),self.animate)

    def paint_frame(self,size):
        if self.big is None or self.rgb_map is None: return
        cw=max(1,self.canvas.winfo_width());ch=max(1,self.canvas.winfo_height())
        image,self.view,close=render_map(self.rgb_map,size,self.pos,self.pixel_chests,
            radius=float(self.ui_config['chest_radius_pixels']),span=self.view_span,
            auto_zoom=self.auto_zoom,view_center=self.last_view_pos,
            view_override=self.motion.view(size),draw_position=self.motion.position,heading=self.motion.heading,
            detail=self.detail_mode)
        self.map_offset=((cw-size)//2,(ch-size)//2)
        if hasattr(self,'tkimg') and self.tkimg.width()==size and self.tkimg.height()==size:
            self.tkimg.paste(image)
            self.canvas.coords(self.map_item,*self.map_offset)
        else:
            self.tkimg=ImageTk.PhotoImage(image)
            self.canvas.delete('all')
            self.map_item=self.canvas.create_image(*self.map_offset,anchor='nw',image=self.tkimg)
        valid=self.pos is not None
        guard_reason=self.guard.reason if hasattr(self,'guard') else ''
        summary=(valid,len(close),self.manual,self.motion.heading is not None,self.auto_zoom,bool(self.pos or self.last_view_pos),self.detail_mode,guard_reason)
        if summary==getattr(self,'_last_summary',None):return
        self._last_summary=summary
        self.count_text.set(str(len(close)) if valid else '—')
        idle='●  PRELOBBY' if hasattr(self,'guard') and self.guard.phase=='prelobby' else '●  PAUSA' if getattr(self,'radar_paused',False) else '●  ATTESA'
        self.live.configure(text=('●  MANUALE' if self.manual else '●  POSIZIONE') if valid else idle,fg=ACCENT if valid else GOLD)
        direction=' · direzione rilevata' if self.motion.heading is not None else ' · direzione non disponibile'
        self.state_text.set(('Posizione manuale' if self.manual else 'Posizione stimata')+direction if valid else guard_reason or 'Posizione non disponibile · ricerca in corso')
        self.mode_text.set('ZOOM DENSITÀ' if self.detail_mode and valid else 'ZOOM LIBERO' if valid else 'IN ATTESA')

    def toggle_detail(self):
        self.detail_mode=not self.detail_mode
        self.detail_button.configure(text='Zoom ampio F6' if self.detail_mode else 'Zoom densità F6')
        self.draw()

    def zoom_by(self,factor):
        self.auto_zoom=True
        self.view_span=max(80,min(1400,self.view_span*factor))
        self.zoom_button.configure(text='Isola intera')
        self.draw()

    def toggle_zoom(self):
        self.auto_zoom=not self.auto_zoom
        self.zoom_button.configure(text='Isola intera' if self.auto_zoom else 'Segui posizione')
        self.draw()

    def toggle_overlay(self):
        if not self.native.available:
            self.status.set('Overlay disponibile su Windows.');return
        if not self.overlay_mode and 0x77 not in self.native.registered_hotkeys:
            self.status.set('Overlay non attivato: F8 deve essere disponibile per tornare al pannello.');return
        self.overlay_mode=not self.overlay_mode
        self.overlay_hidden=False
        self.root.deiconify()
        if self.overlay_mode:
            self.desktop_geometry=self.root.geometry()
            self.root.minsize(1,1)
            self.root.overrideredirect(True)
            for widget in (self.controls,self.tools,self.settings,self.detail): widget.pack_forget()
            self.brand.configure(font=('Segoe UI',11,'bold'))
            self.header.pack_configure(padx=12,pady=(12,8))
            self.metrics.pack_configure(padx=12,pady=(0,6))
            self.map_frame.pack_configure(padx=12)
            # Position on the configured game monitor, outside the source minimap.
            index=self.ui_config.get('monitor_index',1)
            if not 1<=index<len(self.screen.monitors):
                self.status.set('Monitor configurato assente: overlay sul monitor principale; riconfigura la minimappa.')
                index=1
            monitor=self.screen.monitors[index]
            x=monitor['left']+24; y=monitor['top']+150
            self.root.geometry(f'390x510{x:+d}{y:+d}')
            self.root.attributes('-alpha',float(self.ui_config.get('overlay_opacity',.92)))
            self.overlay_locked=True
        else:
            self.native.apply(False,False)
            self.root.overrideredirect(False)
            self.root.minsize(640,720)
            self.root.geometry(self.desktop_geometry)
            self.brand.configure(font=('Segoe UI',15,'bold'))
            self.header.pack_configure(padx=20,pady=(18,12))
            self.metrics.pack_configure(padx=20,pady=(0,10))
            self.map_frame.pack_configure(padx=20)
            for widget in (self.detail,self.settings,self.tools,self.controls): widget.pack(side='bottom',fill='x',padx=20,pady=5,before=self.map_frame)
            self.root.attributes('-alpha',1.0)
        self.root.attributes('-topmost',True)
        self.apply_overlay_style()
        self.schedule_draw()

    def apply_overlay_style(self):
        try:
            self.native.apply(self.overlay_mode,self.overlay_locked)
            self.hint_text.set('F6 Zoom densità · F7 Pausa/Avvia\n'+('F8 Pannello · F9 Sposta · F10 Nascondi' if self.overlay_mode and self.overlay_locked else
                               'F8 Pannello · F9 Blocca · trascina il titolo' if self.overlay_mode else
                               'F8 Overlay · F9 Sblocca · F10 Nascondi'))
        except Exception as exc:
            self.status.set('Overlay non attivato: '+str(exc))
            self.root.overrideredirect(False)
            self.overlay_mode=False

    def poll_hotkeys(self):
        for key in self.native.drain_hotkeys():
            if key==0x75:self.toggle_detail()
            if key==0x76:self.toggle_tracking()
            if key==0x77: self.toggle_overlay()
            if key==0x78 and self.overlay_mode:
                self.overlay_locked=not self.overlay_locked
                self.apply_overlay_style()
            if key==0x79 and self.overlay_mode:
                self.overlay_hidden=not self.overlay_hidden
                if self.overlay_hidden: self.root.withdraw()
                else: self.root.deiconify();self.apply_overlay_style()
        if self.native.hotkey_error:
            self.status.set('Scorciatoie: '+self.native.hotkey_error)
        self.root.after(40,self.poll_hotkeys)

    def notify(self,text):
        self.status.set(text)
        self.notice.configure(text=text)
        self.notice.pack(side='bottom',fill='x',padx=10,pady=3,before=self.map_frame)
        if self._notice_after is not None:self.root.after_cancel(self._notice_after)
        self._notice_after=self.root.after(3000,lambda:self.notice.pack_forget())

    def drag_start(self,event):
        if self.overlay_mode and not self.overlay_locked:
            self._drag=(event.x_root-self.root.winfo_x(),event.y_root-self.root.winfo_y())

    def drag_move(self,event):
        if self._drag and self.overlay_mode and not self.overlay_locked:
            x=event.x_root-self._drag[0];y=event.y_root-self._drag[1]
            self.root.geometry(f'{x:+d}{y:+d}')
