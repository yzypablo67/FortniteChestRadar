import unittest
import math
import cv2
import numpy as np
from heading import HeadingDetector,map_bearing
from motion import Motion,angle_delta
from map_view import Viewport


class MotionTests(unittest.TestCase):
    def test_heading_wraps_short_way(self):
        m=Motion();v=Viewport(0,0,220,300)
        m.step(v,(100,100),359,.033)
        m.step(v,(100,100),1,.033)
        self.assertLess(abs(angle_delta(m.heading,359)),2)
        self.assertGreater(angle_delta(m.heading,359),0)

    def test_interpolation_is_frame_rate_independent(self):
        outcomes=[]
        for fps in (30,60):
            m=Motion();m.step(Viewport(0,0,800,300),(100,100),0,.033)
            for _ in range(fps):m.step(Viewport(100,100,220,300),(140,150),90,1/fps)
            outcomes.append(m)
        self.assertLess(math.dist(outcomes[0].position,outcomes[1].position),.02)
        self.assertLess(abs(outcomes[0].camera[2]-outcomes[1].camera[2]),.03)

    def test_no_extrapolation(self):
        m=Motion();v=Viewport(0,0,220,300)
        m.step(v,(100,100),0,.033)
        for _ in range(100):m.step(v,(120,110),80,.033)
        self.assertLessEqual(m.position[0],120)
        self.assertLessEqual(m.position[1],110)

    def test_loss_clears_marker_and_heading_immediately(self):
        m=Motion();v=Viewport(0,0,220,300)
        m.step(v,(100,100),45,.03);m.step(v,None,None,.03)
        self.assertIsNone(m.position);self.assertIsNone(m.heading)


class HeadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.detector=HeadingDetector()

    def arrow(self,angle):
        frame=np.full((202,202,3),(60,120,35),np.uint8)
        mask=np.zeros((202,202),np.uint8)
        cv2.fillPoly(mask,[np.int32([[101,94],[96,106],[101,103],[106,106]])],255)
        mask=cv2.warpAffine(mask,cv2.getRotationMatrix2D((101,101),-angle,1),(202,202))
        frame[mask>200]=(255,255,255)
        return frame

    def test_directions_not_movement(self):
        for angle in (0,45,90,180,270,350):
            result=self.detector.estimate(self.arrow(angle),[[1,0,0],[0,1,0]])
            self.assertIsNotNone(result,(angle,self.detector.last_report))
            self.assertLess(abs(angle_delta(result,angle)),20)

    def test_rotated_minimap_transform(self):
        # Up on a minimap rotated clockwise by 90 degrees maps east on the reference.
        self.assertAlmostEqual(map_bearing(0,[[0,-1,0],[1,0,0]]),90)

    def test_uniform_and_lines_rejected(self):
        frame=np.zeros((202,202,3),np.uint8)
        self.assertIsNone(self.detector.estimate(frame,[[1,0,0],[0,1,0]]))
        cv2.line(frame,(60,101),(140,101),(255,255,255),2)
        self.assertIsNone(self.detector.estimate(frame,[[1,0,0],[0,1,0]]))

    def test_no_registration_means_no_map_bearing(self):
        self.assertIsNone(self.detector.estimate(self.arrow(0),None))

    def test_ambiguous_round_marker_rejected(self):
        frame=np.zeros((202,202,3),np.uint8)
        cv2.circle(frame,(101,101),5,(255,255,255),-1)
        self.assertIsNone(self.detector.estimate(frame,[[1,0,0],[0,1,0]]))

if __name__=='__main__':unittest.main()
