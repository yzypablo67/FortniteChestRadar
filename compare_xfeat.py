"""Reproducible offline timing comparison; never selects a live position."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from matching import Matcher
from xfeat_matcher import XFeatMatcher
from app_paths import app_root,resource_path


def compare(big,small,model,config=None):
    report={'scope':'single saved image; no live game validation','ground_truth':None,
            'accuracy_improvement_demonstrated':False,'model_bytes':Path(model).stat().st_size}
    for name,factory in [('SIFT',lambda:Matcher(big,config)),('XFeat',lambda:XFeatMatcher(big,model,config))]:
        start=time.perf_counter();matcher=factory();init=(time.perf_counter()-start)*1000
        samples=[]
        for _ in range(4):
            start=time.perf_counter();position=matcher.locate(small);samples.append((time.perf_counter()-start)*1000)
        report[name]={'init_ms':init,'median_ms':float(np.median(samples[1:])),
                      'position':position,'report':matcher.last_report}
    return report


def save_report(report,folder):
    from datetime import datetime
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    target=folder/('xfeat_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
    target.write_text(json.dumps(report,indent=2),encoding='utf-8');return target


def main():
    parser=argparse.ArgumentParser(description='Confronto offline SIFT/XFeat su immagini fornite')
    parser.add_argument('--compare-xfeat',action='store_true')
    parser.add_argument('--map',required=True);parser.add_argument('--minimap',required=True)
    parser.add_argument('--config');parser.add_argument('--out',default=str(app_root()/'diagnostics'))
    args=parser.parse_args()
    big=cv2.imread(args.map);small=cv2.imread(args.minimap)
    if big is None or small is None:parser.error('Immagini non leggibili')
    config=json.loads(Path(args.config).read_text(encoding='utf-8-sig')) if args.config else {}
    report=compare(big,small,resource_path('models/xfeat.onnx'),config)
    save_report(report,args.out)

if __name__=='__main__':main()
