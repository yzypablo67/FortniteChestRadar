import unittest
from session_guard import SessionGuard,blocked_phase
from map_view import viewport,detail_markers,detail_span

STRONG={'best':{'inliers':100,'inlier_ratio':.95,'coverage':.6}}


class SessionTests(unittest.TestCase):
    def test_no_point_before_hud_check(self):
        g=SessionGuard()
        self.assertFalse(g.candidate((100,100),STRONG,1))

    def test_empty_startup_hud_needs_confirmation(self):
        g=SessionGuard();g.update_hud('',0)
        self.assertFalse(g.permitted(1))
        self.assertTrue(g.confirm_manually())
        self.assertTrue(g.permitted(1))

    def test_prelobby_rejects_even_a_perfect_match(self):
        for text in ('IN ATTESA DI GIOCATORI','In attesa dei giocatori','BUS IN PARTENZA TRA 10','WAITING FOR PLAYERS','BATTLE BUS LAUNCHING IN 10'):
            g=SessionGuard();g.update_hud(text,0)
            for t in (1,2,3):self.assertFalse(g.candidate((100,100),STRONG,t),text)
            self.assertFalse(g.confirm_manually())

    def test_live_banner_not_a_prelobby(self):
        for text in ('FRUTTI DEL DIAVOLO GENERATI','La tempesta si restringera tra 30 secondi','63 giocatori rimasti'):
            self.assertIsNone(blocked_phase(text))

    def test_three_consistent_readings_required(self):
        g=SessionGuard();g.update_hud('Partita',0)
        self.assertFalse(g.candidate((100,100),STRONG,1))
        self.assertFalse(g.candidate((101,102),STRONG,1.8))
        self.assertTrue(g.candidate((103,104),STRONG,2.6))

    def test_weak_and_jumping_matches_not_confirmed(self):
        g=SessionGuard();g.update_hud('Partita',0)
        self.assertFalse(g.candidate((100,100),{'best':{'inliers':9}},1))
        for t,p in ((1.2,(100,100)),(2,(900,900)),(2.8,(100,100)),(3.6,(900,900))):
            self.assertFalse(g.candidate(p,STRONG,t))

    def test_ocr_failure_requires_explicit_confirmation(self):
        g=SessionGuard();g.update_hud('',0,False)
        self.assertFalse(g.permitted(1))
        self.assertTrue(g.confirm_manually())
        self.assertTrue(g.permitted(1))
        for _ in range(3):g.failed()
        self.assertFalse(g.permitted(2))

    def test_clear_hud_twice_after_prelobby(self):
        g=SessionGuard();g.update_hud('IN ATTESA DI GIOCATORI',0)
        self.assertFalse(g.update_hud('',2))
        self.assertTrue(g.update_hud('La tempesta',4))
        self.assertTrue(g.permitted(5))

    def test_stale_hud_does_not_enable_a_random_point(self):
        g=SessionGuard();g.update_hud('',0)
        self.assertFalse(g.permitted(8))
        self.assertFalse(g.candidate((100,100),STRONG,8))


class DetailTests(unittest.TestCase):
    def test_dense_markers_keep_true_positions_and_separate_labels(self):
        v=viewport((1000,1000),300,(500,500),80)
        close=[(i*.1,500+i*.1,500) for i in range(22)]
        markers=detail_markers(close,v,(150,150))
        self.assertEqual(len(markers),12)
        self.assertEqual(markers[0]['rank'],1)
        for m in markers:
            self.assertEqual(m['anchor'],v.screen(*m['map_point']))
            self.assertGreaterEqual(((m['x']-150)**2+(m['y']-150)**2)**.5,30)
        for i,a in enumerate(markers):
            for b in markers[i+1:]:
                self.assertGreaterEqual(((a['x']-b['x'])**2+(a['y']-b['y'])**2)**.5,34-1e-6)

    def test_detail_zoom_is_tighter_only_in_dense_zones(self):
        self.assertEqual(detail_span(220,(500,500),[(510,500)]),220)
        self.assertEqual(detail_span(220,(500,500),[(500+i,500) for i in range(10)]),80)

if __name__=='__main__':unittest.main()
