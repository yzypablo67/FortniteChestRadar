"""Run inside the environment installed from requirements-build.txt."""
from pathlib import Path
import os,subprocess,sys,shutil
root=Path(__file__).resolve().parent
if os.name!='nt':raise SystemExit('La build Windows deve essere eseguita su Windows x64.')
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
 '--name','FortniteChestRadar','--noupx',
 '--add-data',str(root/'windows_ocr.ps1')+';.',
 '--add-data',str(root/'assets')+';assets',
 '--add-data',str(root/'models')+';models',
 '--collect-all','onnxruntime',
 '--exclude-module','tokenizers','--exclude-module','torch',
 '--exclude-module','matplotlib','--exclude-module','pytest',
 str(root/'radar.py')],cwd=root,check=True)
release=root/'dist/FortniteChestRadar'
for name in ('config.example.json','GUIDA_CONFIGURAZIONE.md','README.md','THIRD_PARTY.md','LICENSE','RELEASE_NOTES.md'):
 shutil.copy2(root/name,release/name)
shutil.copy2(root/'config.example.json',release/'config.json')
shutil.copytree(root/'licenses',release/'licenses',dirs_exist_ok=True)
for name,argument in [('Avvia overlay','--overlay'),('Configura','--configure'),('Verifica','--self-test')]:
 (release/(name+'.bat')).write_text('@echo off\ncd /d "%~dp0"\nstart "" /wait FortniteChestRadar.exe '+argument+'\n',encoding='ascii')
print(release)
