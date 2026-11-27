"""Download the models into models/ (plain files, no Hugging Face cache).

    python -m live_captions.download                     Whisper large-v3 and NLLB-200 600M (about 5.5 GB)
    python -m live_captions.download --if-missing        only what config.toml / models/ does not have yet
    python -m live_captions.download --whisper small.en  a smaller Whisper instead
    python -m live_captions.download --only nllb

Why a plain folder: the Hugging Face cache uses symbolic links, and on Windows without admin rights or Developer Mode that can
fail with "WinError 1314: A required privilege is not held by the client". Files in models/<name> are found automatically."""
import argparse
import fnmatch
import os
import threading

from . import config
from .config import NLLB_ID, WHISPER_REPOS

WHISPER_FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
NLLB_FILES = ["*.json", "sentencepiece.bpe.model", "pytorch_model.bin"]


def _size(folder):
    n = 0
    for root, _, files in os.walk(folder):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def fetch(repo, dest, patterns, label):
    """Download with a progress line every few seconds (readable in a log, unlike progress bars)."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    from huggingface_hub import HfApi, snapshot_download
    total = 0
    try:
        info = HfApi().model_info(repo, files_metadata=True)
        total = sum(f.size or 0 for f in info.siblings if any(fnmatch.fnmatch(f.rfilename, p) for p in patterns))
    except Exception:
        pass
    print(f"{label}: downloading {repo}" + (f" ({total / 1e9:.1f} GB)" if total else "") + f" into {dest}", flush=True)
    done = threading.Event()

    def report():
        while not done.wait(5):
            got = _size(dest)
            pct = f" ({100 * got / total:.0f}%)" if total else ""
            print(f"{label}: {got / 1e9:.2f} GB{pct}", flush=True)
    threading.Thread(target=report, daemon=True).start()
    try:
        snapshot_download(repo_id=repo, local_dir=dest, allow_patterns=patterns)
    finally:
        done.set()
    print(f"{label}: done", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="live_captions.download", description=__doc__.split("\n")[0])
    ap.add_argument("--dest", default="models", help="folder to download into (default: models)")
    ap.add_argument("--whisper", help=f"Whisper size: {', '.join(WHISPER_REPOS)} (default: the one in config.toml, else large-v3)")
    ap.add_argument("--only", choices=["whisper", "nllb"], help="download only this one")
    ap.add_argument("--if-missing", action="store_true", help="skip a model that config.toml or models/ already has")
    a = ap.parse_args(argv)
    s = config.load()
    size = a.whisper or (s.whisper if s.whisper in WHISPER_REPOS else "large-v3")
    if a.only != "nllb":
        if size not in WHISPER_REPOS:
            ap.error(f"unknown Whisper size {size!r}; choose one of {', '.join(WHISPER_REPOS)}")
        have = s.whisper_model() if (s.whisper == size or os.path.isdir(s.path(s.whisper))) else ""
        if a.if_missing and have and os.path.isfile(os.path.join(have, "model.bin")):
            print(f"Whisper: already there ({have})", flush=True)
        else:
            fetch(WHISPER_REPOS[size], os.path.join(a.dest, f"faster-whisper-{size}"), WHISPER_FILES, "Whisper")
    if a.only != "whisper":
        have = s.nllb_model()
        if a.if_missing and os.path.isfile(os.path.join(have, "config.json")):
            print(f"Translation model: already there ({have})", flush=True)
        else:
            fetch(NLLB_ID, os.path.join(a.dest, NLLB_ID.split("/")[-1]), NLLB_FILES, "Translation model")
    if a.whisper and a.whisper != s.whisper and a.only != "nllb":
        print(f'\nset whisper = "{a.whisper}" under [models] in config.toml to use it', flush=True)


if __name__ == "__main__":
    main()
