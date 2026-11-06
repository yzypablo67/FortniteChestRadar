import sys
import queue
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import radar


class AppTests(unittest.TestCase):
    def app(self):
        app=radar.App.__new__(radar.App)
        app.manual=False; app.pos=(100,200)
        app.status=Mock(); app.info=Mock(); app.draw=Mock()
        app.matcher=Mock(last_report={'reason':'Rifiuto verificato'})
        app.events=queue.Queue(); app.generation=2
        app.pose_revision=0;app.heading=None;app.orientation_matrix=None
        from session_guard import SessionGuard
        app.guard=SessionGuard()
        app.radar_paused=False
        return app

    def test_rejected_result_clears_marker(self):
        app=self.app(); app.apply_result(None)
        self.assertIsNone(app.pos); app.draw.assert_called_once()
        app.status.set.assert_called_with('Rifiuto verificato')

    def test_error_clears_marker(self):
        app=self.app(); app.apply_error('Errore cattura')
        self.assertIsNone(app.pos)

    def test_old_map_index_ignored(self):
        app=self.app(); old=app.matcher
        app.set_matcher(Mock(),1)
        self.assertIs(app.matcher,old)

    def test_callbacks_run_when_drained(self):
        app=self.app(); callback=Mock()
        app.post(callback); callback.assert_not_called()
        app.events.get_nowait()(); callback.assert_called_once()

    def test_manual_not_overwritten(self):
        app=self.app(); app.manual=True
        app.apply_result((1,2,10)); self.assertEqual(app.pos,(100,200))

    def test_prelobby_clears_marker_and_old_zoom(self):
        app=self.app();app.last_view_pos=(100,200)
        app.apply_hud('IN ATTESA DI GIOCATORI',1,True)
        self.assertIsNone(app.pos);self.assertIsNone(app.last_view_pos)
        app.apply_result((100,200,100))
        self.assertIsNone(app.pos)

    def test_queued_match_from_before_phase_change_ignored(self):
        app=self.app();old_epoch=app.guard.epoch
        app.guard.update_hud('BUS IN PARTENZA TRA 10',1)
        app.matcher.locate.return_value=(100,200,100)
        app.apply_result=Mock()
        app.match_async(None,app.matcher,old_epoch)
        while not app.events.empty():app.events.get_nowait()()
        app.apply_result.assert_not_called()

class AsyncErrorTests(unittest.TestCase):
    app=AppTests.app
    def test_old_match_error_does_not_clear_new_position(self):
        app=self.app();old=Mock();old.locate.side_effect=RuntimeError('old map')
        app.match_async(None,old,app.guard.epoch)
        while not app.events.empty():app.events.get_nowait()()
        self.assertEqual(app.pos,(100,200))

    def test_old_phase_error_is_ignored(self):
        app=self.app();epoch=app.guard.epoch
        app.guard.update_hud('BUS IN PARTENZA TRA 10',1)
        app.matcher.locate.side_effect=RuntimeError('old phase')
        app.apply_error=Mock();app.match_async(None,app.matcher,epoch)
        while not app.events.empty():app.events.get_nowait()()
        app.apply_error.assert_not_called()

if __name__=='__main__': unittest.main()
