"""Recording, only while switched on (R): sessions/<date-time>/audio.wav (left = speaker output, right = microphone, 16 kHz)
and captions.txt (the caption lines with times from the start of the recording)."""
import datetime
import os
import threading
import time
import wave

import numpy as np

from .config import SR


class Recorder:
    def __init__(self, sessions_dir="sessions"):
        self.sessions_dir = sessions_dir
        self.on, self.t0, self.dir = False, None, None
        self.wav, self.log, self.lock = None, None, threading.Lock()
        self.buf = {"them": [], "me": []}

    def toggle(self):
        with self.lock:
            if self.on:
                self._flush(final=True)
                self.wav.close()
                self.log.close()
                self.on = False
                return f"saved: {self.dir}"
            self.dir = os.path.join(self.sessions_dir, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
            os.makedirs(self.dir)
            self.wav = wave.open(os.path.join(self.dir, "audio.wav"), "wb")
            self.wav.setnchannels(2)
            self.wav.setsampwidth(2)
            self.wav.setframerate(SR)
            self.log = open(os.path.join(self.dir, "captions.txt"), "w", encoding="utf-8")
            self.log.write("Live captions (automatic, Whisper + NLLB; not checked). Times from the start of the recording.\n\n")
            self.buf = {"them": [], "me": []}
            self.t0 = time.time()
            self.on = True
            return "recording"

    def add(self, who, x):
        if self.on:
            with self.lock:
                self.buf[who].append(x)
                self._flush()

    def _flush(self, final=False):
        """Write as many stereo frames as both sides have (or only the speaker side, if the mic is silent/missing)."""
        a, b = [np.concatenate(self.buf[k]) if self.buf[k] else np.zeros(0, np.float32) for k in ("them", "me")]
        if final:
            n = max(len(a), len(b))
        elif len(a) and len(b):
            n = min(len(a), len(b))
        else:
            n = len(a) if len(a) > SR else 0
        if not n:
            return
        a2, b2 = np.zeros(n, np.float32), np.zeros(n, np.float32)
        a2[:min(n, len(a))] = a[:n]
        b2[:min(n, len(b))] = b[:n]
        self.wav.writeframes((np.clip(np.stack([a2, b2], 1), -1, 1) * 32767).astype(np.int16).tobytes())
        self.buf = {"them": [a[n:]] if len(a) > n else [], "me": [b[n:]] if len(b) > n else []}

    def line(self, who, en, th):
        if self.on:
            s = int(time.time() - self.t0)
            with self.lock:
                self.log.write(f"[{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}] {who}: {en}\n            {th}\n")
                self.log.flush()

    def elapsed(self):
        return int(time.time() - self.t0) if self.on else 0
