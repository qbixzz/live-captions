"""Window check without a person (GPU and models needed): a muted rehearsal feed, then scroll back and resize from code,
with a screenshot after each step.

    python -X utf8 tests/test_window.py <audio file> [--start S] [--out tests/out] [--wait 70]"""
import argparse
import os
import queue
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_captions import config  # noqa: E402
from live_captions.audio import Audio  # noqa: E402
from live_captions.captioner import Captioner  # noqa: E402
from live_captions.recorder import Recorder  # noqa: E402
from live_captions.window import Window  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--out", default=os.path.join("tests", "out"))
    ap.add_argument("--wait", type=float, default=70, help="seconds of captions before the first screenshot")
    ap.add_argument("--config")
    a = ap.parse_args()
    from PIL import ImageGrab
    os.makedirs(a.out, exist_ok=True)
    s = config.load(a.config)
    ui_q, rec = queue.Queue(), Recorder(s.path(s.sessions_dir))
    audio = Audio(a.audio, a.start, mute=True)
    cap = Captioner(ui_q, rec, s)
    # visible to screenshots, and its own window-state file so your saved position is not touched
    win = Window(ui_q, cap, rec, audio, s, hide_from_capture=False, state_file=os.path.join(a.out, "window.json"))
    threading.Thread(target=lambda: (cap.load(), audio.run(), cap.run(audio)), daemon=True).start()
    r = win.root

    def snap(name):  # the caption window only
        r.update_idletasks()
        x, y, w_, h = r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w_, y + h), all_screens=True).save(os.path.join(a.out, name))

    def resize():  # as if the corner were dragged 300 px left and 120 px down
        class E:
            pass
        e = E()
        e.x_root, e.y_root = 1000, 1000
        win._grab(e)
        e.x_root, e.y_root = 700, 1120
        win._resize(e, "se")

    w = int(a.wait * 1000)
    r.after(w, lambda: snap("1_latest.png"))
    r.after(w + 1000, lambda: win.text.yview_scroll(-6, "units"))
    r.after(w + 2500, lambda: snap("2_scrolled_back.png"))
    r.after(w + 3000, resize)
    r.after(w + 4500, lambda: snap("3_resized.png"))
    r.after(w + 5000, win.quit)
    r.mainloop()
    print("lines:", len(win.lines), "screenshots in", a.out, flush=True)
    os._exit(0)  # skip interpreter shutdown while the caption threads still run


if __name__ == "__main__":
    main()
