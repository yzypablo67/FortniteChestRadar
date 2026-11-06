"""Offline portable build smoke test; no game input, network or global hotkeys."""
import sys,json
from pathlib import Path
from app_paths import app_root,resource_path

def main():
    import cv2,numpy as np,tkinter as tk
    import onnxruntime,mss
    from matching import Matcher
    rng=np.random.default_rng(54)
    image=np.full((800,800,3),60,np.uint8)
    for _ in range(2400):
        x,y=rng.integers(0,800,2);r=int(rng.integers(2,10))
        cv2.circle(image,(int(x),int(y)),r,tuple(int(v) for v in rng.integers(20,240,3)),-1)
    matcher=Matcher(image);result=matcher.locate(image[250:470,250:470].copy())
    if result is None or np.linalg.norm(np.array(result[:2])-[360,360])>3:raise RuntimeError('Matching test fallito')
    root=tk.Tk();root.withdraw();root.update_idletasks();root.destroy()
    if not resource_path('windows_ocr.ps1').exists():raise RuntimeError('Risorsa OCR mancante')
    from map_view import chest_icon
    if chest_icon().width<20:raise RuntimeError('Icona cassa mancante')
    report={'ok':True,'version':'0.2.0-experimental','frozen':bool(getattr(sys,'frozen',False)),
            'opencv':cv2.__version__,'onnxruntime':onnxruntime.__version__,
            'synthetic_match_error':float(np.linalg.norm(np.array(result[:2])-[360,360])),
            'tk_available':True,'ocr_script_bundled':True,'network_used':False,'game_input_sent':False,
            'config_modified':False,'does_not_validate_live_gameplay':True}
    target=app_root()/'self-test.json'
    index=sys.argv.index('--self-test')
    if len(sys.argv)>index+1:target=Path(sys.argv[index+1])
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
