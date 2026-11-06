import json
import sys
import unittest
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matching import Matcher
from diagnostics import validate_config, save_bundle
import tempfile


def terrain(seed=12):
    rng=np.random.default_rng(seed)
    im=np.full((900,1000,3),60,np.uint8)
    for _ in range(2400):
        x,y=rng.integers([0,0],[1000,900]); r=int(rng.integers(2,12))
        cv2.circle(im,(int(x),int(y)),r,tuple(int(v) for v in rng.integers(30,240,3)),-1)
    return cv2.GaussianBlur(im,(3,3),.5)


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.big=terrain(); cls.matcher=Matcher(cls.big)

    def crop(self,angle=0,scale=1.,center=(530,440)):
        a=np.deg2rad(angle)
        A=np.array([[scale*np.cos(a),-scale*np.sin(a),0],
                    [scale*np.sin(a),scale*np.cos(a),0]],np.float64)
        A[:,2]=np.array(center)-A[:,:2]@np.array([120,120])
        return cv2.warpAffine(self.big,A,(240,240),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP)

    def check_position(self,im,expected=(530,440)):
        cv2.setRNGSeed(42)
        result=self.matcher.locate(im)
        self.assertIsNotNone(result,self.matcher.last_report)
        self.assertLess(np.linalg.norm(np.array(result[:2])-expected),5)

    def test_exact_crop(self): self.check_position(self.crop())
    def test_rotation_and_scale(self): self.check_position(self.crop(37,1.65))
    def test_zoom_in(self): self.check_position(self.crop(-22,.7))
    def test_hud_and_color(self):
        im=self.crop(12,1.2)
        im=cv2.convertScaleAbs(im,alpha=.8,beta=25)
        cv2.putText(im,'HUD',(20,200),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),3)
        cv2.circle(im,(120,120),8,(255,255,255),-1)
        self.check_position(im)
    def test_black(self): self.assertIsNone(self.matcher.locate(np.zeros((200,200,3),np.uint8)))
    def test_tiny(self): self.assertIsNone(self.matcher.locate(np.zeros((20,20,3),np.uint8)))
    def test_unrelated(self): self.assertIsNone(self.matcher.locate(terrain(88)[100:340,100:340]))
    def test_repeated_texture(self):
        tile=np.zeros((200,200,3),np.uint8)
        for y in range(0,200,20):
            for x in range(0,200,20): cv2.circle(tile,(x+5,y+5),3,(200,200,200),-1)
        self.assertIsNone(self.matcher.locate(tile))
    def test_invalid_config(self):
        base={'minimap_bbox_1920':[1,1,200,200]}
        validate_config(base)
        for change in ({'minimap_bbox_1920':[3,2,1,4]},{'monitor_index':0},{'player_anchor':[2,.5]},{'matching_every_seconds':0},{'overlay_opacity':0},{'view_span_pixels':float('nan')},{'overlay_on_start':'true'}):
            with self.assertRaises(ValueError): validate_config(dict(base,**change))
    def test_bundle(self):
        self.matcher.locate(self.crop())
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            out=save_bundle(d,self.crop(),self.matcher)
            report=json.loads((out/'report.json').read_text())
            self.assertTrue(report['accepted'])
            self.assertNotIn('api_key',json.dumps(report))
            self.assertTrue((out/'matches.png').exists())


if __name__=='__main__': unittest.main(verbosity=2)
