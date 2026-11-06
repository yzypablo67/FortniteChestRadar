"""Time-based visual interpolation; no extrapolation or invented player movement."""
import math
from map_view import Viewport


def angle_delta(target,current):
    return (target-current+180)%360-180


class Motion:
    def __init__(self):
        self.camera=None
        self.position=None
        self.heading=None

    def step(self,target_view,target_position,target_heading,dt):
        # Exponential interpolation is independent of render frame rate.
        alpha=1-math.exp(-max(0,min(dt,.25))/.12)
        angle_alpha=1-math.exp(-max(0,min(dt,.25))/.07)
        camera=(target_view.left,target_view.top,target_view.side)
        changed=False
        if self.camera is None:self.camera=camera;changed=True
        old_camera=self.camera
        self.camera=tuple(b if abs(b-a)<.02 else a+(b-a)*alpha for a,b in zip(self.camera,camera))
        changed|=self.camera!=old_camera
        old_position=self.position
        if target_position is None:self.position=None
        elif self.position is None or math.dist(self.position,target_position)>target_view.side*1.5:
            self.position=tuple(target_position)
        else:self.position=tuple(b if abs(b-a)<.01 else a+(b-a)*alpha for a,b in zip(self.position,target_position))
        changed|=self.position!=old_position
        old_heading=self.heading
        if target_heading is None:self.heading=None
        elif self.heading is None:self.heading=target_heading%360
        else:
            delta=angle_delta(target_heading,self.heading)
            self.heading=(target_heading if abs(delta)<.05 else self.heading+delta*angle_alpha)%360
        changed|=self.heading!=old_heading
        return changed

    def view(self,size):
        return Viewport(*self.camera,size)
