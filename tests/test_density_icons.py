import unittest
from unittest.mock import patch
from PIL import Image
from map_view import detail_span,render_map

class DensityIconTests(unittest.TestCase):
    def test_more_chests_tighten_zoom_until_limit(self):
        spans=[detail_span(220,(500,500),[(510+i*.1,500) for i in range(n)]) for n in (0,1,2,4,8,16)]
        self.assertEqual(spans[0],220)
        self.assertTrue(all(a>=b for a,b in zip(spans,spans[1:])))
        self.assertLess(spans[3],spans[2]);self.assertEqual(spans[-1],80)

    def test_icon_stays_at_coordinate_in_both_zoom_modes(self):
        for detail in (True,False):
            with patch('map_view.chest_icon',return_value=Image.new('RGBA',(4,4),'red')):
                image,v,_=render_map(Image.new('RGB',(1000,1000),'black'),300,(500,500),[(530,500)],span=100,detail=detail)
            x,y=v.screen(530,500)
            self.assertEqual(image.getpixel((round(x),round(y))),(255,0,0))
            self.assertEqual(image.getpixel((200,150)),(0,0,0))
            self.assertEqual(image.getpixel((round(x)+15,round(y))),(0,0,0))
