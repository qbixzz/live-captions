"""Quick checks that need no GPU, models or sound card:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import time
import unittest
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_captions import config  # noqa: E402
from live_captions.captioner import quiet_cut  # noqa: E402
from live_captions.config import SR  # noqa: E402
from live_captions.recorder import Recorder  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfig(unittest.TestCase):
    def test_example_config_loads(self):
        s = config.load(os.path.join(REPO, "config.example.toml"))
        self.assertEqual(s.whisper, "large-v3")
        self.assertEqual(s.pause, 0.45)
        self.assertEqual(s.base, REPO)

    def test_unknown_setting_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            fn = os.path.join(d, "config.toml")
            with open(fn, "w") as f:
                f.write('[models]\nwhisperr = "small.en"\n')
            with self.assertRaises(ValueError):
                config.load(fn)

    def test_relative_paths_and_local_models(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "models", "nllb-200-distilled-600M"))
            fn = os.path.join(d, "config.toml")
            with open(fn, "w") as f:
                f.write('[captions]\nterms_file = "my terms.txt"\npause = 1\n[recording]\nsessions_dir = "rec"\n')
            with open(os.path.join(d, "my terms.txt"), "w", encoding="utf-8") as f:
                f.write("# comment\nAlpha, Beta\n\n Gamma \n")
            s = config.load(fn)
            self.assertIsInstance(s.pause, float)
            self.assertEqual(s.terms(), ["Alpha", "Beta", "Gamma"])
            self.assertEqual(s.path(s.sessions_dir), os.path.join(d, "rec"))
            self.assertEqual(s.nllb_model(), os.path.join(d, "models", "nllb-200-distilled-600M"))
            self.assertEqual(s.whisper_model(), "large-v3")  # not downloaded locally: the name is passed on

    def test_prompt(self):
        self.assertIsNone(config.build_prompt("", []))
        self.assertEqual(config.build_prompt("A team meeting.", ["API", "KPI"]), "A team meeting. API, KPI.")
        self.assertEqual(config.build_prompt("", ["API"]), "API.")

    def test_example_terms(self):
        terms = config.read_terms(os.path.join(REPO, "terms.example.txt"))
        self.assertIn("OAuth", terms)
        self.assertFalse(any(t.startswith("#") for t in terms))


class TestSegmenting(unittest.TestCase):
    def test_quiet_cut_finds_the_gap(self):
        a = np.full(8 * SR, 0.3, np.float32)
        gap = 7 * SR  # quiet 0.3 s, 1 s before the end
        a[gap:gap + int(0.3 * SR)] = 0
        cut = quiet_cut(a)
        self.assertTrue(len(a) - int(2.5 * SR) < cut <= len(a))
        self.assertTrue(gap <= cut <= gap + int(0.3 * SR) + int(0.15 * SR), cut)


class TestRecorder(unittest.TestCase):
    def test_stereo_file_and_log(self):
        with tempfile.TemporaryDirectory() as d:
            rec = Recorder(d)
            self.assertEqual(rec.toggle(), "recording")
            for _ in range(3):  # like the captioner: both sides added in turn, 0.5 s each; the mic stops early
                rec.add("them", np.full(SR // 2, 0.5, np.float32))
                if _ < 2:
                    rec.add("me", np.full(SR // 2, -0.5, np.float32))
            rec.add("them", np.full(SR // 2, 0.5, np.float32))
            rec.line("them", "Hello.", "สวัสดี")
            time.sleep(0.01)
            msg = rec.toggle()
            self.assertTrue(msg.startswith("saved: "))
            with wave.open(os.path.join(rec.dir, "audio.wav")) as w:
                self.assertEqual((w.getnchannels(), w.getframerate(), w.getnframes()), (2, SR, SR * 2))
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2)
            self.assertGreater(x[0, 0], 0)          # left = them
            self.assertLess(x[0, 1], 0)             # right = me
            self.assertEqual(x[-1, 1], 0)           # mic shorter: padded with silence
            with open(os.path.join(rec.dir, "captions.txt"), encoding="utf-8") as f:
                log = f.read()
            self.assertIn("them: Hello.", log)
            self.assertIn("สวัสดี", log)


if __name__ == "__main__":
    unittest.main()
