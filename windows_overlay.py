"""Windows-only external overlay; no hooks, injection or game process access."""
import os
import ctypes
import threading
import queue
from ctypes import wintypes


class WindowsOverlay:
    def __init__(self,root):
        self.root=root
        self.available=os.name=='nt'
        self.previous={}
        self.hotkeys=queue.Queue()
        self.hotkey_error=None
        self.registered_hotkeys=set()
        self.hotkey_thread_id=None
        self.hotkey_ready=threading.Event()
        if not self.available: return
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        self.user.GetAncestor.restype=wintypes.HWND
        pointer=ctypes.c_ssize_t
        self.get_style=self.user.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else self.user.GetWindowLongW
        self.set_style=self.user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else self.user.SetWindowLongW
        self.get_style.argtypes=[wintypes.HWND,ctypes.c_int]; self.get_style.restype=pointer
        self.set_style.argtypes=[wintypes.HWND,ctypes.c_int,pointer]; self.set_style.restype=pointer
        self.user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        self.user.SetWindowPos.restype=wintypes.BOOL
        self.user.GetAsyncKeyState.argtypes=[ctypes.c_int];self.user.GetAsyncKeyState.restype=ctypes.c_short
        self.user.GetForegroundWindow.restype=wintypes.HWND
        self.user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        self.user.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        self.user.RegisterHotKey.restype=wintypes.BOOL
        self.user.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
        self.user.GetMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT]
        self.user.GetMessageW.restype=ctypes.c_int
        self.user.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
        self.user.PostThreadMessageW.argtypes=[wintypes.DWORD,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.hotkey_thread=threading.Thread(target=self.listen_hotkeys,daemon=True,name='radar-hotkeys')
        self.hotkey_thread.start()

    def listen_hotkeys(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentThreadId.restype=wintypes.DWORD
        self.hotkey_thread_id=kernel.GetCurrentThreadId()
        message=wintypes.MSG()
        self.user.PeekMessageW(ctypes.byref(message),None,0,0,0)
        registered=[]
        try:
            for key in (0x75,0x76,0x77,0x78,0x79):
                if not self.user.RegisterHotKey(None,key,0x4000,key):
                    self.hotkey_error=(self.hotkey_error+'; ' if self.hotkey_error else '')+f'F{key-0x70+1} già usato da un altro programma'
                    continue
                registered.append(key)
                self.registered_hotkeys.add(key)
            self.hotkey_ready.set()
            while True:
                result=self.user.GetMessageW(ctypes.byref(message),None,0,0)
                if result==0: break
                if result<0: raise ctypes.WinError(ctypes.get_last_error())
                if message.message==0x0312:
                    self.hotkeys.put(int(message.wParam))
        except Exception as exc:
            self.hotkey_error=str(exc)
        finally:
            for key in registered: self.user.UnregisterHotKey(None,key)
            self.registered_hotkeys.clear()
            self.hotkey_ready.set()

    def drain_hotkeys(self):
        result=[]
        while True:
            try: result.append(self.hotkeys.get_nowait())
            except queue.Empty: return result

    def close(self):
        if self.available and self.hotkey_thread_id:
            self.user.PostThreadMessageW(self.hotkey_thread_id,0x0012,0,0)

    def apply(self,enabled,locked):
        if not self.available: return
        self.root.update_idletasks()
        hwnd=self.user.GetAncestor(self.root.winfo_id(),2)
        if not hwnd: raise ctypes.WinError(ctypes.get_last_error())
        flags=self.get_style(hwnd,-20)
        # LAYERED is managed by Tk opacity. Only toggle our interaction flags.
        flags &= ~(0x20|0x08000000|0x80)
        if enabled:
            flags |= 0x80
            if locked: flags |= 0x20|0x08000000
        ctypes.set_last_error(0)
        result=self.set_style(hwnd,-20,flags)
        if result==0 and ctypes.get_last_error(): raise ctypes.WinError(ctypes.get_last_error())
        # Refresh frame without moving, resizing or activating the game/overlay.
        if not self.user.SetWindowPos(hwnd,wintypes.HWND(-1 if enabled else -2),0,0,0,0,0x1|0x2|0x10|0x20):
            raise ctypes.WinError(ctypes.get_last_error())
        return flags

    def pressed(self,key):
        if not self.available: return False
        down=bool(self.user.GetAsyncKeyState(key)&0x8000)
        edge=down and not self.previous.get(key,False)
        self.previous[key]=down
        return edge

    def game_foreground(self):
        if not self.available: return True
        hwnd=self.user.GetForegroundWindow()
        text=ctypes.create_unicode_buffer(512)
        self.user.GetWindowTextW(hwnd,text,len(text))
        return text.value.strip().lower()=='fortnite'
