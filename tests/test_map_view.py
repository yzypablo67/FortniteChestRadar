import unittest
from PIL import Image
from map_view import viewport,render_map,nearby,marker_groups


class ViewTests(unittest.TestCase):
    def test_zoom_centers_and_roundtrip(self):
        v=viewport((2048,2048),340,(900,1000),300)
        self.assertEqual(v.screen(900,1000),(170,170))
        self.assertEqual(v.map_point(170,170),(900,1000))

    def test_edge_clamps_without_losing_player(self):
        v=viewport((2048,2048),340,(8,2040),300)
        self.assertEqual(v.left,0); self.assertEqual(v.top,1748)
        x,y=v.screen(8,2040)
        self.assertTrue(0<=x<340 and 0<=y<340)

    def test_overview_preserves_rectangular_aspect(self):
        v=viewport((400,800),400)
        self.assertEqual(v.screen(400,200),(200,200))
        self.assertEqual(v.side,800)

    def test_no_position_has_no_chest_claim(self):
        image,view,close=render_map(Image.new('RGB',(800,800)),300,None,[(100,100)])
        self.assertEqual(close,[])
        self.assertEqual(view.side,800)

    def test_lost_position_retains_view_without_markers(self):
        _,v,close=render_map(Image.new('RGB',(800,800)),300,None,[(100,100)],view_center=(300,300))
        self.assertEqual(v.side,300);self.assertEqual(close,[])

    def test_distance_filter_and_nearest(self):
        self.assertEqual(nearby([(50,50),(10,0),(3,4)],(0,0),10),[(5.,3,4),(10.,10,0)])

    def test_zoom_increases_marker_separation(self):
        full=viewport((2048,2048),340)
        zoom=viewport((2048,2048),340,(900,1000),300)
        distance=lambda v:v.screen(930,1000)[0]-v.screen(900,1000)[0]
        self.assertGreater(distance(zoom),distance(full)*6)

    def test_dense_groups_preserve_counts_and_nearest(self):
        v=viewport((1000,1000),300,(500,500),220)
        points=[(1,501,500),(2,502,500),(4,504,500),(60,560,500)]
        groups=marker_groups(points,v)
        self.assertEqual(sum(g['count'] for g in groups),4)
        self.assertEqual(len(groups),2)
        self.assertEqual(sum(g['nearest'] for g in groups),1)
        self.assertEqual(next(g['count'] for g in groups if g['nearest']),3)

    def test_group_markers_do_not_collide(self):
        v=viewport((1000,1000),300,(500,500),220)
        close=[(abs(i),500+i,500+(i%3)*5) for i in range(-60,61,5)]
        groups=marker_groups(close,v)
        self.assertEqual(sum(g['count'] for g in groups),len(close))
        for i,a in enumerate(groups):
            for b in groups[i+1:]:
                self.assertGreaterEqual((a['x']-b['x'])**2+(a['y']-b['y'])**2,38**2)

if __name__=='__main__':unittest.main()
