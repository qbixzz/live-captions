"""The caption window's logic, without models or sound: python -m unittest discover -s tests
(It creates a hidden Tk window, so it needs a desktop session.)"""
import os
import queue
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_captions import config  # noqa: E402
from live_captions.window import Window  # noqa: E402


class FakeCap:
    paused = mic_captions = False


class FakeRec:
    def __init__(self):
        self.on, self.toggles = False, 0

    def toggle(self):
        self.on, self.toggles = not self.on, self.toggles + 1
        return "recording" if self.on else "saved: somewhere"

    def elapsed(self):
        return 0


class FakeAudio:
    def __init__(self):
        self.level, self.names, self.errors = {"them": 0.0, "me": 0.0}, {"them": "Speakers"}, []
        self.mic_ok, self.stop = True, threading.Event()


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "window.json")
        self.make()

    def make(self):
        self.q, self.cap, self.rec, self.audio = queue.Queue(), FakeCap(), FakeRec(), FakeAudio()
        self.win = Window(self.q, self.cap, self.rec, self.audio, config.Settings(), hide_from_capture=False,
                          state_file=self.state)
        self.win.root.withdraw()
        self.win.root.update()

    def tearDown(self):
        try:
            self.win.root.destroy()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_recording_needs_two_presses(self):
        self.win.toggle_rec()
        self.assertFalse(self.rec.on)
        self.win.toggle_rec()
        self.assertTrue(self.rec.on)
        self.win.toggle_rec()  # stopping is one press
        self.assertFalse(self.rec.on)

    def test_recording_press_expires(self):
        self.win.toggle_rec()
        self.win._armed["rec"] = time.time() - 1
        self.win.toggle_rec()
        self.assertFalse(self.rec.on)

    def test_escape_needs_two_presses(self):
        self.win.escape()
        self.assertTrue(self.win.root.winfo_exists())
        self.win.escape()
        self.assertTrue(self.audio.stop.is_set())
        self.assertTrue(os.path.isfile(self.state))

    def test_lines_and_compact(self):
        self.q.put(("status", "ready"))
        for i in range(4):
            self.q.put(("final", "them", f"Line {i}.", f"บรรทัด {i}", 0.5))
        self.q.put(("final", "me", "Mine.", "ของฉัน", 0.5))
        self.win.poll()
        self.assertEqual(len(self.win.lines), 5)
        self.assertFalse(self.win.placeholder.winfo_ismapped())
        old = self.win.text.tag_ranges("th_old")
        self.assertTrue(old)  # earlier lines are dimmed
        self.assertIn("You · ของฉัน", self.win.text.get("1.0", "end"))
        h = self.win.h
        self.win.toggle_compact()
        self.assertLess(self.win.h, h)
        self.assertFalse(self.win.show_en)
        self.win.toggle_compact()
        self.assertEqual(self.win.h, h)
        self.assertTrue(self.win.show_en)

    def test_state_is_remembered(self):
        self.win.font(4)
        self.win.toggle_en()
        self.win.set_opacity(0.8)
        self.win.toggle_pin()
        self.win.quit()
        self.make()
        self.assertEqual(self.win.size, 26)
        self.assertFalse(self.win.show_en)
        self.assertAlmostEqual(self.win.opacity, 0.8)
        self.assertFalse(self.win.pinned)
        self.assertEqual(self.win.root.attributes("-topmost"), 0)

    def test_error_status(self):
        self.q.put(("status", "error: CUDA is not available"))
        self.win.poll()
        self.assertEqual(self.win.state, "error")
        self.assertIn("CUDA is not available", self.win.placeholder.cget("text"))


if __name__ == "__main__":
    unittest.main()
