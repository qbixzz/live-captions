"""Download the models into models/ (plain files, no Hugging Face cache).

    python -m live_captions.download                     Whisper large-v3 and NLLB-200 600M (about 5.5 GB)
    python -m live_captions.download --whisper small.en  a smaller Whisper instead
    python -m live_captions.download --only nllb

Why a plain folder: the Hugging Face cache uses symbolic links, and on Windows without admin rights or Developer Mode that can
fail with "WinError 1314: A required privilege is not held by the client". Files in models/<name> are found automatically."""
import argparse
import os

from .config import NLLB_ID, WHISPER_REPOS

WHISPER_FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
NLLB_FILES = ["*.json", "sentencepiece.bpe.model", "pytorch_model.bin"]


def fetch(repo, dest, patterns):
    from huggingface_hub import snapshot_download
    print(f"downloading {repo} -> {dest}", flush=True)
    snapshot_download(repo_id=repo, local_dir=dest, allow_patterns=patterns)
    print(f"done: {dest}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="live_captions.download", description=__doc__.split("\n")[0])
    ap.add_argument("--dest", default="models", help="folder to download into (default: models)")
    ap.add_argument("--whisper", default="large-v3", help=f"Whisper size: {', '.join(WHISPER_REPOS)}")
    ap.add_argument("--only", choices=["whisper", "nllb"], help="download only this one")
    a = ap.parse_args(argv)
    if a.only != "nllb":
        if a.whisper not in WHISPER_REPOS:
            ap.error(f"unknown Whisper size {a.whisper!r}; choose one of {', '.join(WHISPER_REPOS)}")
        fetch(WHISPER_REPOS[a.whisper], os.path.join(a.dest, f"faster-whisper-{a.whisper}"), WHISPER_FILES)
    if a.only != "whisper":
        fetch(NLLB_ID, os.path.join(a.dest, NLLB_ID.split("/")[-1]), NLLB_FILES)
    if a.whisper != "large-v3" and a.only != "nllb":
        print(f'\nset whisper = "{a.whisper}" under [models] in config.toml to use it', flush=True)


if __name__ == "__main__":
    main()
