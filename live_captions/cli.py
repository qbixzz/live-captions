"""Command line: python -m live_captions [options]. See README.md."""
import argparse
import os
import queue
import threading

from . import config
from .audio import Audio
from .captioner import Captioner
from .recorder import Recorder
from .window import Window


def parser():
    ap = argparse.ArgumentParser(prog="live_captions",
                                 description="Live English captions with a Thai translation, in a window that stays on top.")
    ap.add_argument("--config", help="settings file (default: config.toml in the current folder, if there is one)")
    ap.add_argument("--sim", metavar="FILE", help="rehearse with an audio or video file instead of the speaker output")
    ap.add_argument("--start", type=float, default=0, help="seconds into the --sim file")
    ap.add_argument("--mute", action="store_true", help="--sim without playing the sound")
    ap.add_argument("--whisper", "--model", dest="whisper", help="Whisper model: size (large-v3, …) or a local folder")
    ap.add_argument("--nllb", help="NLLB translation model: Hugging Face id or a local folder")
    ap.add_argument("--terms", help="terms file for Whisper (default: terms.txt)")
    ap.add_argument("--device", choices=["cuda", "cpu"], help="cuda (default) or cpu (very slow)")
    ap.add_argument("--sessions", help="folder for recordings (default: sessions)")
    ap.add_argument("--quit-after", type=float, default=0, help="close by itself after this many seconds (for tests)")
    ap.add_argument("--snap", help="with --quit-after: save a screenshot here 2 s before closing (for tests)")
    return ap


def settings_from(a):
    """Settings from the config file, with any command-line options on top (paths given on the command line are taken
    relative to the current folder)."""
    s = config.load(a.config)
    if a.whisper:
        s.whisper = os.path.abspath(a.whisper) if os.path.isdir(a.whisper) else a.whisper
    if a.nllb:
        s.nllb = os.path.abspath(a.nllb) if os.path.isdir(a.nllb) else a.nllb
    if a.terms:
        s.terms_file = os.path.abspath(a.terms)
    if a.device:
        s.device = a.device
    if a.sessions:
        s.sessions_dir = os.path.abspath(a.sessions)
    return s


def describe(s):
    terms = s.terms()
    lines = [f"[config] {s.config_file or 'no config.toml, using defaults'}",
             f"[config] whisper: {s.whisper_model()} ({s.device}, {s.compute()})",
             f"[config] translation: {s.nllb_model()}"]
    tf = s.path(s.terms_file) if s.terms_file else ""
    if terms:
        lines.append(f"[config] terms: {len(terms)} from {tf}")
    else:
        lines.append(f"[config] terms: none ({tf or 'no terms file'} not found; copy terms.example.txt to terms.txt to add some)")
    prompt = s.prompt() or ""
    if len(prompt) > 800:
        lines.append(f"[config] note: the terms are long ({len(prompt)} characters); Whisper only uses about the last 220 tokens")
    lines.append(f"[config] recordings go to: {s.path(s.sessions_dir)}")
    return "\n".join(lines)


def main(argv=None):
    a = parser().parse_args(argv)
    s = settings_from(a)
    print(describe(s), flush=True)
    ui_q, rec = queue.Queue(), Recorder(s.path(s.sessions_dir))
    audio = Audio(a.sim, a.start, mute=a.mute)
    cap = Captioner(ui_q, rec, s)
    win = Window(ui_q, cap, rec, audio, s)
    if a.quit_after:
        if a.snap:
            from PIL import ImageGrab
            win.root.after(int((a.quit_after - 2) * 1000), lambda: ImageGrab.grab(all_screens=True).save(a.snap))
        win.root.after(int(a.quit_after * 1000), win.quit)

    def boot():
        try:
            cap.load()
            audio.run()
            cap.run(audio)
        except Exception as e:
            import traceback
            traceback.print_exc()
            ui_q.put(("status", f"error: {e}"))
    threading.Thread(target=boot, daemon=True).start()
    win.root.mainloop()


if __name__ == "__main__":
    main()
