"""Prevent two portable instances from competing for hotkeys/configuration."""
import ctypes,hashlib,os
from pathlib import Path
_handle=None

def acquire(folder):
    global _handle
    if os.name!='nt':return True
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    name='Local\\FortniteChestRadar_'+hashlib.sha256(str(Path(folder).resolve()).lower().encode()).hexdigest()[:24]
    handle=kernel.CreateMutexW(None,False,name)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
        return False
    _handle=handle
    return True
