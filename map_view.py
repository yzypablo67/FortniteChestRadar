"""Shared map geometry and raster renderer for desktop and overlay."""
from dataclasses import dataclass
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from app_paths import resource_path


@dataclass(frozen=True)
class Viewport:
    left: float
    top: float
    side: float
    size: int

    def screen(self,x,y):
        return ((x-self.left)*self.size/self.side,(y-self.top)*self.size/self.side)

    def map_point(self,x,y):
        return (self.left+x*self.side/self.size,self.top+y*self.side/self.size)


def viewport(shape,size,position=None,span=300):
    h,w=shape[:2]
    if position is None:
        side=max(h,w)
        return Viewport((w-side)/2,(h-side)/2,side,size)
    side=max(64,min(float(span),max(w,h)))
    x,y=position
    left=max(0,min(x-side/2,w-side)) if side<=w else (w-side)/2
    top=max(0,min(y-side/2,h-side)) if side<=h else (h-side)/2
    return Viewport(left,top,side,size)


def nearby(points,position,radius):
    if position is None: return []
    x,y=position
    return sorted((math.hypot(px-x,py-y),px,py) for px,py in points if math.hypot(px-x,py-y)<=radius)


def marker_groups(close,view,spacing=38):
    """Merge screen-space collisions, preserving every visible spawn and nearest identity."""
    groups=[]
    for index,(_,x,y) in enumerate(close):
        sx,sy=view.screen(x,y)
        if 8<=sx<=view.size-8 and 8<=sy<=view.size-8:
            groups.append({'x':sx,'y':sy,'count':1,'nearest':index==0})
    while True:
        best=None;distance=spacing*spacing
        for i,a in enumerate(groups):
            for j in range(i+1,len(groups)):
                b=groups[j];d=(a['x']-b['x'])**2+(a['y']-b['y'])**2
                if d<distance:distance=d;best=(i,j)
        if best is None:break
        i,j=best;a,b=groups[i],groups[j];count=a['count']+b['count']
        groups[i]={'x':(a['x']*a['count']+b['x']*b['count'])/count,
                   'y':(a['y']*a['count']+b['y']*b['count'])/count,
                   'count':count,'nearest':a['nearest'] or b['nearest']}
        groups.pop(j)
    return groups


def detail_markers(close,view,player,limit=12):
    """Separate labels while retaining the true 2D spawn anchor on the terrain."""
    result=[]
    obstacles=[(player[0],player[1],30),(view.size-24,24,28)]
    for rank,(_,x,y) in enumerate(close):
        px,py=view.screen(x,y)
        if not (4<=px<=view.size-4 and 4<=py<=view.size-4):continue
        if len(result)>=limit:break
        direction=math.atan2(py-player[1],px-player[0])
        placed=None
        for radius in (0,28,44,60,80,104,132):
            for step in range(16 if radius else 1):
                angle=direction+step*math.tau/16
                sx,sy=px+radius*math.cos(angle),py+radius*math.sin(angle)
                if not (20<=sx<=view.size-20 and 20<=sy<=view.size-20):continue
                if any(math.hypot(sx-ox,sy-oy)<distance for ox,oy,distance in obstacles):continue
                placed=(sx,sy);break
            if placed is not None:break
        if placed is None:continue
        sx,sy=placed;obstacles.append((sx,sy,40))
        result.append({'rank':rank+1,'x':sx,'y':sy,'anchor':(px,py),'map_point':(x,y),'nearest':rank==0})
    return result


def detail_span(base,position,points):
    if position is None:return base
    # Count within a fixed map radius, independent of the current viewport:
    # denser surroundings progressively tighten the zoom without feedback loops.
    count=len(nearby(points,position,110))
    if count<=1:return base
    return min(base,max(80,base/math.sqrt(1+.8*(count-1))))



@lru_cache(maxsize=8)
def label_font(size):
    for name in ('C:/Windows/Fonts/seguisb.ttf','DejaVuSans-Bold.ttf'):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()


@lru_cache(maxsize=4)
def chest_icon(size=44):
    """User-selected Fortnite.GG artwork, loaded once without runtime networking."""
    with Image.open(resource_path('assets/chest.png')) as source:
        icon=source.convert('RGBA')
    bbox=icon.getbbox()
    if bbox:icon=icon.crop(bbox)
    icon.thumbnail((size,size),Image.Resampling.LANCZOS)
    return icon


def render_map(rgb,size,position,points,radius=110,span=300,auto_zoom=True,view_center=None,
               heading=None,view_override=None,draw_position=None,detail=False):
    view=view_override or viewport((rgb.height,rgb.width),size,(position or view_center) if auto_zoom else None,span)
    # EXTENT preserves fractional coordinates and aspect ratio without stretching the island.
    image=rgb.transform((size,size),Image.Transform.EXTENT,
                        (view.left,view.top,view.left+view.side,view.top+view.side),
                        resample=Image.Resampling.BILINEAR,fillcolor='#101a28').convert('RGB')
    draw=ImageDraw.Draw(image,'RGBA')
    close=nearby(points,position,radius)
    if position is not None:
        cx,cy=view.screen(*(draw_position or position))
        if heading is not None:
            a=math.radians(heading)
            forward=(math.sin(a),-math.cos(a));right=(math.cos(a),math.sin(a))
            cone=[(cx,cy)]
            for offset in range(-28,29,4):
                direction=math.radians(heading+offset)
                cone.append((cx+math.sin(direction)*60,cy-math.cos(direction)*60))
            draw.polygon(cone,fill=(82,242,225,38))
        r=radius*size/view.side
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(110,230,222,90),width=1)
        # Icons stay exactly on their map coordinates: no leaders or displacement.
        icon=chest_icon()
        for _,x,y in reversed(close):
            sx,sy=view.screen(x,y)
            if not (-20<=sx<=size+20 and -20<=sy<=size+20):continue
            image.paste(icon,(round(sx-icon.width/2),round(sy-icon.height/2)),icon)
        draw.ellipse((cx-10,cy-10,cx+10,cy+10),fill=(16,27,42,230),outline=(246,255,255,255),width=2)
        if heading is None:
            draw.ellipse((cx-3,cy-3,cx+3,cy+3),fill=(82,242,225,255))
        else:
            shape=[]
            for side,front in ((0,8),(-5,-5),(0,-2),(5,-5)):
                shape.append((cx+right[0]*side+forward[0]*front,cy+right[1]*side+forward[1]*front))
            draw.polygon(shape,fill=(82,242,225,255))
    # A consistent north cue; map remains north-up, including when the game minimap rotates.
    draw.rounded_rectangle((size-38,10,size-10,38),radius=8,fill=(10,18,29,225))
    draw.text((size-29,17),'N',fill=(218,236,244,255))
    return image,view,close
