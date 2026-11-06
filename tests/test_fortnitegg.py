import json
import unittest
from pathlib import Path
import tempfile
import cv2
import numpy as np
from fortnitegg import parse_spawns, public_script, associated_chests, fingerprint, align_to_reference

class FortniteGGTests(unittest.TestCase):
    def test_coordinate_conversion_and_groups(self):
        text='window.Spawns='+json.dumps({'chests':[{'coords':[[-64,128],[-64,128]]},{'coords':[[-128,64]]}]})+';'
        self.assertEqual(parse_spawns(text),[(.25,.5),(.5,.25)])

    def test_no_javascript_execution(self):
        with self.assertRaises(ValueError): parse_spawns('window.Spawns={}; alert(1)')

    def test_unknown_schema(self):
        with self.assertRaises(ValueError): parse_spawns('window.Spawns={"items":[]}')

    def test_invalid_coordinate(self):
        for value in ([1,20],[-64,300],[-64,'20']):
            with self.assertRaises(ValueError): parse_spawns('window.Spawns='+json.dumps({'chests':[{'coords':[value]}]}))

    def test_public_origin_only(self):
        self.assertEqual(public_script("<script src='/data/en.js?v=1'></script>",'en'),'https://fortnite.gg/data/en.js?v=1')
        with self.assertRaises(ValueError): public_script('<script src="https://example.org/data/en.js"></script>','en')

    def test_map_hash_binding(self):
        image=np.zeros((50,50,3),np.uint8)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            p=Path(folder)/'map.png'
            (p.with_name('chests.json')).write_text(json.dumps({'map_sha256':fingerprint(image),'points':[[12,24]]}))
            self.assertEqual(associated_chests(p,image),[(12,24)])
            image[0,0]=255
            with self.assertRaises(ValueError): associated_chests(p,image)

    def test_reference_alignment(self):
        from test_matching import terrain
        source=terrain()
        matrix=np.array([[.95,0,18],[0,.95,20]],np.float64)
        reference=cv2.warpAffine(source,matrix,(1000,900))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            image,data,path=align_to_reference(source,reference,{'points':[[500,400]],'source':'test'},folder)
            self.assertLess(np.linalg.norm(np.array(data['points'][0])-[493,400]),2)
            self.assertEqual(associated_chests(path,image),[tuple(data['points'][0])])

    def test_unrelated_reference_rejected(self):
        from test_matching import terrain
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with self.assertRaises(ValueError):
                align_to_reference(terrain(),terrain(99),{'points':[[500,400]]},folder)

if __name__=='__main__': unittest.main()
