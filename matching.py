"""Pixel-only minimap registration. No game/process access."""
import cv2
import numpy as np


class Matcher:
    def __init__(self, big, config=None):
        if big is None or big.size == 0:
            raise ValueError('Mappa vuota')
        self.big = big
        self.cfg = config or {}
        self.detector = cv2.SIFT_create(nfeatures=18000, contrastThreshold=0.018)
        self.refs = []
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        # Retain fine detail as well as coarser features; coordinates remain in map pixels.
        for scale in sorted(set([min(1., 2600/max(gray.shape)), min(1., 1400/max(gray.shape))])):
            ref = cv2.resize(gray, None, fx=scale, fy=scale)
            kp, desc = self.detector.detectAndCompute(ref, None)
            self.refs.append((scale, kp, desc))
        self.last_report = {}
        self.last_visual = None

    def locate(self, small):
        self.last_report = {'accepted': False, 'reason': 'Nessun allineamento valido', 'attempts': []}
        self.last_visual = small.copy()
        h, w = small.shape[:2]
        if min(h,w) < 48:
            self.last_report['reason'] = 'Ritaglio troppo piccolo (minimo 48 pixel)'
            return None
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if gray.std() < 4:
            self.last_report['reason'] = 'Ritaglio uniforme/nero: controllare cattura e finestra del gioco'
            return None
        mask = np.full((h,w), 255, np.uint8)
        border = max(3, round(min(h,w)*.04))
        mask[:border] = mask[-border:] = 0
        mask[:,:border] = mask[:,-border:] = 0
        # Configurable anchor: the player must be at this point in the captured minimap.
        ax, ay = self.cfg.get('player_anchor', [.5,.5])
        cv2.circle(mask, (round(ax*w),round(ay*h)), max(4,round(min(h,w)*.045)), 0, -1)
        for x1,y1,x2,y2 in self.cfg.get('excluded_rects', []):
            mask[round(y1*h):round(y2*h),round(x1*w):round(x2*w)] = 0
        candidates = []
        for zoom in (1., 2.):
            q = cv2.resize(gray, None, fx=zoom, fy=zoom)
            qm = cv2.resize(mask, (q.shape[1],q.shape[0]), interpolation=cv2.INTER_NEAREST)
            qkp, qdesc = self.detector.detectAndCompute(q,qm)
            for scale, rkp, rdesc in self.refs:
                report = {'query_zoom': zoom, 'reference_scale': scale, 'keypoints':len(qkp)}
                self.last_report['attempts'].append(report)
                if qdesc is None or rdesc is None or len(rdesc)<2:
                    report['reason'] = 'Dettagli insufficienti'; continue
                pairs = cv2.BFMatcher().knnMatch(qdesc,rdesc,k=2)
                good = [p[0] for p in pairs if len(p)==2 and p[0].distance < .75*p[1].distance]
                # A reference feature cannot count multiple times as independent evidence.
                unique = {}
                for m in sorted(good,key=lambda m:m.distance):
                    unique.setdefault(m.trainIdx,m)
                good = list(unique.values())
                report['matches'] = len(good)
                if len(good)<8:
                    report['reason'] = 'Meno di 8 corrispondenze univoche'; continue
                src = np.float32([qkp[m.queryIdx].pt for m in good])/zoom
                dst = np.float32([rkp[m.trainIdx].pt for m in good])/scale
                # The minimap is a rotated/scaled top-down crop, not an arbitrary perspective plane.
                A, flags = cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,
                    ransacReprojThreshold=3/scale,maxIters=4000,confidence=.999,refineIters=20)
                if A is None or flags is None:
                    report['reason'] = 'Geometria non stimabile'; continue
                valid = flags.ravel().astype(bool)
                n = int(valid.sum()); ratio = n/len(good)
                spread = cv2.contourArea(cv2.convexHull(src[valid]))/(w*h) if n>=3 else 0
                error = float(np.median(np.linalg.norm(cv2.transform(src[None],A)[0][valid]-dst[valid],axis=1)))
                factor = float(np.hypot(A[0,0],A[1,0]))
                point = A @ np.array([ax*w,ay*h,1.])
                report.update(inliers=n,inlier_ratio=ratio,coverage=spread,median_error=error,scale=factor)
                bh,bw = self.big.shape[:2]
                if n<8 or ratio<.45 or spread<.08 or error>3/scale:
                    report['reason'] = 'Supporto geometrico insufficiente'; continue
                if not (.15 <= factor <= 20 and 0 <= point[0]<bw and 0<=point[1]<bh and factor*w<bw*.9 and factor*h<bh*.9):
                    report['reason'] = 'Scala o posizione fuori dai limiti'; continue
                report['reason'] = 'Candidato valido'
                candidates.append((n,point,A,report,src,dst,valid))
        if not candidates:
            self.last_report['reason'] = 'Matching rifiutato: controllare dettagli tentativi, mappa/modalita, ritaglio e zoom'
            return None
        candidates.sort(key=lambda c:c[0],reverse=True)
        best = candidates[0]
        if any(np.linalg.norm(c[1]-best[1])>max(20,best[3]['scale']*min(w,h)*.15) for c in candidates[1:]):
            self.last_report['reason'] = 'Risultati discordanti tra scale: posizione ambigua'
            return None
        n,point,A,report,src,dst,valid = best
        self.last_report.update(accepted=True,reason='Stima geometrica accettata, da verificare in gioco',
                                position=point.tolist(),best=report,map_transform=A.tolist())
        ref = cv2.resize(self.big,(600,600))
        visual = np.zeros((max(h,600),w+600,3),np.uint8)
        visual[:h,:w] = small; visual[:600,w:] = ref
        bh,bw = self.big.shape[:2]
        for s,d in zip(src[valid],dst[valid]):
            cv2.line(visual,tuple(np.int32(s)),(w+int(d[0]*600/bw),int(d[1]*600/bh)),(0,255,0),1)
        self.last_visual = visual
        return float(point[0]),float(point[1]),n
