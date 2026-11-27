"""Headless check of the whole pipeline (GPU and models needed; no window, no sound card): feeds part of an audio file at
real-time pace and prints the captions and timings.

    python -X utf8 tests/test_pipeline.py <audio file> [--start S] [--seconds N] [--config config.toml]

No file at hand? tests/make_sample_audio.ps1 makes an English sample with Windows text-to-speech."""
import argparse
import os
import queue
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_captions import config  # noqa: E402
from live_captions.audio import Audio, read_file  # noqa: E402
from live_captions.captioner import Captioner  # noqa: E402
from live_captions.cli import describe  # noqa: E402
from live_captions.config import SR  # noqa: E402
from live_captions.recorder import Recorder  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--seconds", type=float, default=0, help="how much of the file (default: all)")
    ap.add_argument("--config")
    a = ap.parse_args()
    s = config.load(a.config)
    print(describe(s), flush=True)
    pcm = read_file(a.audio, a.start, a.seconds or None)
    dur = len(pcm) / SR
    ui_q, rec = queue.Queue(), Recorder(s.path(s.sessions_dir))
    cap = Captioner(ui_q, rec, s)
    t = time.time()
    cap.load()
    print(f"models loaded in {time.time() - t:.1f}s; feeding {dur:.0f}s of audio", flush=True)
    audio = Audio()

    def feed():
        for i in range(0, len(pcm), SR // 10):
            audio.q_them.put(pcm[i:i + SR // 10])
            time.sleep(0.1)
        audio.q_them.put(np.zeros(SR, np.float32))  # a second of quiet at the end, so the last line finishes

    # time each transcription (beam 1 = the yellow partial line, beam 5 = the final line)
    orig, times = cap._text, []

    def timed(x, beam):
        t = time.time()
        r = orig(x, beam)
        times.append((beam, len(x) / SR, time.time() - t))
        return r
    cap._text = timed
    threading.Thread(target=feed, daemon=True).start()
    threading.Thread(target=cap.run, args=(audio,), daemon=True).start()
    t0 = time.time()
    end, finals = t0 + dur + 6, 0
    while time.time() < end:
        try:
            m = ui_q.get(timeout=0.5)
        except queue.Empty:
            continue
        if m[0] == "final":
            finals += 1
            print(f"[{time.time() - t0:5.1f}s] EN: {m[2]}\n          TH: {m[3]}\n"
                  f"          (Thai shown {m[4]:.1f}s after the pause was detected)", flush=True)
    p = [x for x in times if x[0] == 1]
    fi = [x for x in times if x[0] == 5]
    print(f"partials: {len(p)}, avg {np.mean([x[2] for x in p]):.2f}s for avg {np.mean([x[1] for x in p]):.1f}s audio" if p else "no partials")
    print(f"finals: {len(fi)}, avg {np.mean([x[2] for x in fi]):.2f}s for avg {np.mean([x[1] for x in fi]):.1f}s audio" if fi else "no finals")
    if s.device == "cuda":
        import torch
        print(f"GPU memory {torch.cuda.max_memory_allocated() / 1e9:.1f} GB (torch part only)")
    sys.exit(0 if finals else 1)


if __name__ == "__main__":
    main()
