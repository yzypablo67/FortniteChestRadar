"""Estimate the white player-arrow direction, never the movement bearing."""
import math
import cv2
import numpy as np


def map_bearing(angle,matrix):
    a=math.radians(angle)
    vector=np.asarray(matrix,dtype=float)[:2,:2]@np.array([math.sin(a),-math.cos(a)])
    return math.degrees(math.atan2(vector[0],-vector[1]))%360


class HeadingDetector:
    def __init__(self,anchor=(.5,.5)):
        self.anchor=anchor
        self.templates=[]
        # White arrow silhouette: north-facing tip, two back corners, central notch.
        for radius in (5,6,7,8):
            glyph=np.zeros((25,25),np.uint8)
            cv2.fillPoly(glyph,[np.int32([[12,12-radius],[12-radius*.68,12+radius*.65],
                                         [12,12+radius*.28],[12+radius*.68,12+radius*.65]])],1)
            for angle in range(0,360,5):
                rotation=cv2.getRotationMatrix2D((12,12),-angle,1)
                template=cv2.warpAffine(glyph,rotation,(25,25),flags=cv2.INTER_NEAREST).astype(np.float32)
                self.templates.append((angle,template,float(template.sum())))
        self.last_report={}

    def estimate(self,frame,matrix):
        self.last_report={'accepted':False,'reason':'Freccia non distinguibile'}
        if frame is None or matrix is None:return None
        h,w=frame.shape[:2]
        if min(h,w)<48:return None
        # Normalize HUD scaling to the original 202px minimap before evaluating the icon.
        normalized=cv2.resize(frame,(202,202),interpolation=cv2.INTER_LINEAR)
        ax,ay=[round(v*202) for v in self.anchor]
        if ax<15 or ay<15 or ax>=187 or ay>=187:return None
        patch=normalized[ay-14:ay+15,ax-14:ax+15].astype(np.int16)
        lo=patch.min(axis=2);hi=patch.max(axis=2)
        white=((lo>=205)&(hi-lo<=45)).astype(np.float32)
        # Isolate the centered icon from the white route/storm lines around it.
        count,labels,stats,centers=cv2.connectedComponentsWithStats(white.astype(np.uint8),8)
        candidates=[]
        for label in range(1,count):
            x,y,bw,bh,area=stats[label]
            distance=float(np.min(np.sum((np.argwhere(labels==label)-[14,14])**2,axis=1)))
            if 12<=area<=180 and 4<=bw<=20 and 4<=bh<=20 and distance<=9:
                candidates.append((distance,label))
        if not candidates:return None
        label=min(candidates)[1]
        white=(labels==label).astype(np.float32)
        sums=cv2.matchTemplate(white,np.ones((25,25),np.float32),cv2.TM_CCORR)
        if white.sum()<12:return None
        scores=[]
        for angle,template,count in self.templates:
            overlap=cv2.matchTemplate(white,template,cv2.TM_CCORR)
            score=2*overlap/(sums+count+1e-6)
            _,best,_,offset=cv2.minMaxLoc(score)
            # Keep the template centered at the configured player anchor (within 2px).
            scores.append((best,angle,offset))
        scores.sort(reverse=True)
        score,angle,offset=scores[0]
        competitor=max(s[0] for s in scores if abs((s[1]-angle+180)%360-180)>=60)
        margin=score-competitor
        self.last_report.update(score=score,margin=margin,minimap_bearing=angle)
        contours,_=cv2.findContours(white.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea)
        hull=cv2.convexHull(contour,returnPoints=False)
        defects=cv2.convexityDefects(contour,hull) if len(hull)>=3 and len(contour)>3 else None
        geometric=None
        if defects is not None:
            defect=max(defects[:,0,:],key=lambda d:d[3])
            depth=defect[3]/256
            notch=contour[defect[2],0].astype(float)
            vertices=contour[:,0,:].astype(float)
            tip=vertices[np.argmax(np.sum((vertices-notch)**2,axis=1))]
            vector=tip-notch
            if depth>=1.1 and np.linalg.norm(vector)>=5:
                value=math.degrees(math.atan2(vector[0],-vector[1]))%360
                if abs((value-angle+180)%360-180)<=30:
                    geometric=value
        if score<.58 or (margin<.035 and geometric is None):
            self.last_report['reason']='Forma della freccia debole o direzione ambigua'
            return None
        angle=geometric if geometric is not None else angle
        self.last_report['minimap_bearing']=angle
        self.last_report['method']='notch_and_template' if geometric is not None else 'template'
        bearing=map_bearing(angle,matrix)
        self.last_report.update(accepted=True,reason='Freccia bianca riconosciuta',map_bearing=bearing)
        return bearing
