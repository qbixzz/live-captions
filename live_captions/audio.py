"""Audio in: the speaker output (WASAPI loopback, i.e. everyone in the call), the default microphone, or a rehearsal file."""
import os
import queue
import shutil
import subprocess
import threading
import time

import numpy as np
from scipy.signal import resample_poly

from .config import SR


def read_file(fn, start=0.0, seconds=None):
    """Decode any audio or video file to 16 kHz mono float32 with ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg was not found on PATH; it is needed to read audio files (see README, Install)")
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(start)]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-i", fn, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)


class Audio:
    """Feeds 16 kHz mono float32 blocks: q_them (speaker output or the rehearsal file) and q_me (microphone)."""

    def __init__(self, sim=None, start=0.0, mute=False):
        self.q_them, self.q_me = queue.Queue(), queue.Queue()
        self.sim, self.start, self.mute = sim, start, mute
        self.stop = threading.Event()
        self.mic_ok = False

    def run(self):
        """One PyAudio for all streams, opened one after another (two PyAudio instances set up at once in two threads can hang)."""
        import pyaudiowpatch as pyaudio
        self.pa, self.streams = pyaudio.PyAudio(), []
        if self.sim:
            threading.Thread(target=self._sim, daemon=True).start()
        else:
            self._loopback()
        self._mic()
        threading.Thread(target=self._close_on_stop, daemon=True).start()

    def _close_on_stop(self):
        self.stop.wait()
        for st in self.streams:
            try:
                st.close()
            except Exception:
                pass

    def _open(self, dev, q, name):
        import pyaudiowpatch as pyaudio
        rate, ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxInputChannels"]))

        def cb(data, n, t, s):
            x = np.frombuffer(data, np.int16).astype(np.float32) / 32768.0
            if ch > 1:
                x = x.reshape(-1, ch).mean(axis=1)
            q.put(resample_poly(x, SR, rate).astype(np.float32) if rate != SR else x)
            return (None, pyaudio.paContinue)

        st = self.pa.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True, input_device_index=dev["index"],
                          frames_per_buffer=int(rate * 0.1), stream_callback=cb)
        print(f"[audio] {name}: {dev['name']} ({rate} Hz, {ch} ch)", flush=True)
        return st

    def _loopback(self):
        try:
            dev = self.pa.get_default_wasapi_loopback()
            st = self._open(dev, self.q_them, "speaker output")
            st.start_stream()
            self.streams.append(st)
        except Exception as e:
            print("[audio] speaker output not opened:", e, flush=True)

    def _mic(self):
        import pyaudiowpatch as pyaudio
        try:
            api = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = self.pa.get_device_info_by_index(api["defaultInputDevice"])
            st = self._open(dev, self.q_me, "microphone")
            st.start_stream()
            self.streams.append(st)
            self.mic_ok = True
        except Exception as e:
            print("[audio] microphone not opened:", e, flush=True)

    def _sim(self):
        """Rehearsal: play the file through the speakers and feed the same audio, in step, 0.1 s at a time."""
        import pyaudiowpatch as pyaudio
        pcm = read_file(self.sim, self.start)
        print(f"[sim] {os.path.basename(self.sim)}: {len(pcm) / SR / 60:.1f} min from {self.start:.0f} s", flush=True)
        out = None if self.mute else self.pa.open(format=pyaudio.paFloat32, channels=1, rate=SR, output=True)
        n = SR // 10
        for i in range(0, len(pcm), n):
            if self.stop.is_set():
                break
            blk = pcm[i:i + n]
            if out:
                out.write(blk.tobytes())  # blocks for 0.1 s: real-time pace
            else:
                time.sleep(0.1)
            self.q_them.put(blk)
        if out:
            out.close()
        print("[sim] end of file", flush=True)
