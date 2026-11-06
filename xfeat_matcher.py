"""Optional CPU XFeat experiment. No network, game access or hidden downloads."""
import hashlib,time
from pathlib import Path
import cv2
import numpy as np

MODEL_SHA256='41336466bbbb09b701b815e33932c7da69cff6ab75a068230418468430482912'

class XFeatMatcher:
    def __init__(self,big,model,config=None):
        import onnxruntime as ort
        if hashlib.sha256(Path(model).read_bytes()).hexdigest()!=MODEL_SHA256:
            raise ValueError('Modello XFeat non verificato')
        self.big=big;self.cfg=config or {};self.last_report={};self.last_visual=None
        opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model),sess_options=opt,providers=['CPUExecutionProvider'])
        parts=[];descriptors=[]
        h,w=big.shape[:2]
        for y in range(0,h,480):
            for x in range(0,w,480):
                tile=big[y:min(y+640,h),x:min(x+640,w)]
                if min(tile.shape[:2])<48:continue
                points,desc=self.extract(tile,max_side=640)
                keep=(points[:,0]<min(480,w-x))&(points[:,1]<min(480,h-y))
                parts.append(points[keep]+[x,y]);descriptors.append(desc[keep])
        self.ref_points=np.concatenate(parts).astype(np.float32)
        self.ref_desc=np.concatenate(descriptors).astype(np.float32)

    def extract(self,image,max_side=512):
        h,w=image.shape[:2];scale=min(1.,max_side/max(h,w))
        image=cv2.resize(image,(max(32,round(w*scale)),max(32,round(h*scale))))
        tensor=cv2.cvtColor(image,cv2.COLOR_BGR2RGB).transpose(2,0,1)[None].astype(np.float32)/255
        points,desc,scores=self.session.run(None,{'images':tensor})
        actual=np.array([image.shape[1]/w,image.shape[0]/h],np.float32)
        return np.asarray(points,np.float32)/actual,np.asarray(desc,np.float32)

    def locate(self,small):
        started=time.perf_counter();self.last_visual=small.copy()
        self.last_report={'accepted':False,'backend':'XFeat CPU','reason':'XFeat: supporto insufficiente','attempts':[]}
        h,w=small.shape[:2]
        if min(h,w)<48 or small.std()<4:return None
        pts,desc=self.extract(small)
        ax,ay=self.cfg.get('player_anchor',[.5,.5])
        mask=(pts[:,0]>w*.04)&(pts[:,0]<w*.96)&(pts[:,1]>h*.04)&(pts[:,1]<h*.96)
        mask&=np.linalg.norm(pts-[ax*w,ay*h],axis=1)>min(h,w)*.045
        for x1,y1,x2,y2 in self.cfg.get('excluded_rects',[]):
            mask&=~((pts[:,0]>=x1*w)&(pts[:,0]<x2*w)&(pts[:,1]>=y1*h)&(pts[:,1]<y2*h))
        pts,desc=pts[mask],desc[mask]
        if len(desc)<8 or len(self.ref_desc)<8:return None
        matcher=cv2.BFMatcher(cv2.NORM_L2)
        pairs=matcher.knnMatch(desc,self.ref_desc,k=2)
        reverse=matcher.match(self.ref_desc,desc)
        good=[p[0] for p in pairs if len(p)==2 and p[0].distance<.6 and reverse[p[0].trainIdx].trainIdx==p[0].queryIdx]
        self.last_report.update(query_keypoints=len(desc),reference_keypoints=len(self.ref_desc),matches=len(good))
        if len(good)<8:return None
        src=np.float32([pts[m.queryIdx] for m in good]);dst=np.float32([self.ref_points[m.trainIdx] for m in good])
        A,flags=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=4,maxIters=4000,confidence=.999,refineIters=20)
        if A is None or flags is None:return None
        valid=flags.ravel().astype(bool);n=int(valid.sum());ratio=n/len(good)
        spread=cv2.contourArea(cv2.convexHull(src[valid]))/(w*h) if n>=3 else 0
        error=float(np.median(np.linalg.norm(cv2.transform(src[None],A)[0][valid]-dst[valid],axis=1)))
        factor=float(np.hypot(A[0,0],A[1,0]));point=A@np.array([ax*w,ay*h,1.]);bh,bw=self.big.shape[:2]
        best={'inliers':n,'inlier_ratio':ratio,'coverage':spread,'median_error':error,'scale':factor,'matches':len(good)}
        self.last_report.update(best=best,elapsed_ms=(time.perf_counter()-started)*1000)
        if n<8 or ratio<.45 or spread<.08 or error>4:return None
        if not (.15<=factor<=20 and 0<=point[0]<bw and 0<=point[1]<bh and factor*w<bw*.9 and factor*h<bh*.9):return None
        self.last_report.update(accepted=True,reason='XFeat: geometria accettata, sperimentale',position=point.tolist(),map_transform=A.tolist())
        return float(point[0]),float(point[1]),n
