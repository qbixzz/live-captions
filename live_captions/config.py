"""Settings: built-in defaults, then config.toml (if there is one), then command-line options.

Relative paths in config.toml are relative to the folder that holds config.toml. With no config file they are relative to the
current folder (the launch scripts change to the repo folder first)."""
import os
import tomllib
from dataclasses import dataclass, fields

SR = 16000
NLLB_ID = "facebook/nllb-200-distilled-600M"
WHISPER_REPOS = {  # model size -> Hugging Face repo that faster-whisper downloads from
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "medium.en": "Systran/faster-whisper-medium.en",
    "small.en": "Systran/faster-whisper-small.en",
}
# Whisper sometimes "hears" these in silence or noise; a line that is only one of them is dropped.
JUNK = {"thank you.", "thanks for watching.", "thank you for watching.", "you", "bye.", ".", "so", "okay."}

SECTIONS = {
    "models": ("whisper", "nllb", "device", "compute_type"),
    "captions": ("terms_file", "context", "pause", "max_len"),
    "recording": ("sessions_dir",),
    "window": ("font_size", "thai_font", "latin_font", "opacity", "hide_from_capture"),
}


@dataclass
class Settings:
    base: str = "."                  # folder that relative paths start from
    config_file: str = ""            # the config.toml that was read, if any
    # [models]
    whisper: str = "large-v3"        # model size, Hugging Face id, or a local folder
    nllb: str = NLLB_ID              # Hugging Face id or a local folder
    device: str = "cuda"             # "cuda" (NVIDIA GPU) or "cpu" (very slow with large-v3)
    compute_type: str = "auto"       # "auto" = float16 on cuda, int8 on cpu
    # [captions]
    terms_file: str = "terms.txt"    # names and terms Whisper should expect, one or more per line
    context: str = ""                # optional sentence before the terms, e.g. "A meeting about cloud hosting."
    pause: float = 0.45              # a caption line ends after this many seconds of quiet ...
    max_len: float = 8.0             # ... or at this many seconds of speech (cut at the quietest point)
    # [recording]
    sessions_dir: str = "sessions"
    # [window]
    font_size: int = 22
    thai_font: str = "Leelawadee UI"
    latin_font: str = "Segoe UI"
    opacity: float = 1.0
    hide_from_capture: bool = True   # keep the window out of screen sharing and screenshots (Windows 10 2004 or newer)

    def path(self, p):
        p = os.path.expanduser(os.path.expandvars(p))
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(self.base, p))

    def whisper_model(self):
        """A local folder if `whisper` is one, or models/faster-whisper-<size> if it was downloaded there; else the name as is."""
        return self._model(self.whisper, f"faster-whisper-{self.whisper}")

    def nllb_model(self):
        return self._model(self.nllb, self.nllb.rstrip("/").split("/")[-1])

    def _model(self, value, local_name):
        if os.path.isdir(self.path(value)):
            return self.path(value)
        local = self.path(os.path.join("models", local_name))
        return local if os.path.isdir(local) else value

    def compute(self):
        if self.compute_type != "auto":
            return self.compute_type
        return "float16" if self.device == "cuda" else "int8"

    def terms(self):
        fn = self.path(self.terms_file) if self.terms_file else ""
        return read_terms(fn) if fn and os.path.isfile(fn) else []

    def prompt(self):
        return build_prompt(self.context, self.terms())


def load(config_file=None):
    """Read config.toml. With no file named, use ./config.toml if it exists, else the defaults."""
    if config_file is None:
        cand = os.path.abspath("config.toml")
        if not os.path.isfile(cand):
            return Settings(base=os.getcwd())
        config_file = cand
    config_file = os.path.abspath(config_file)
    with open(config_file, "rb") as f:
        data = tomllib.load(f)
    s = Settings(base=os.path.dirname(config_file), config_file=config_file)
    types = {f.name: f.type for f in fields(Settings)}
    for sec, values in data.items():
        if sec not in SECTIONS:
            raise ValueError(f"{config_file}: unknown section [{sec}] (expected one of {', '.join(SECTIONS)})")
        for k, v in values.items():
            if k not in SECTIONS[sec]:
                raise ValueError(f"{config_file}: unknown setting '{k}' in [{sec}] (expected one of {', '.join(SECTIONS[sec])})")
            t = types[k] if isinstance(types[k], type) else type(getattr(s, k))
            setattr(s, k, t(v))
    return s


def read_terms(fn):
    """Terms file: one or more terms per line, separated by commas. Blank lines and lines starting with # are ignored."""
    terms = []
    with open(fn, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            terms.extend(t.strip() for t in line.split(",") if t.strip())
    return terms


def build_prompt(context, terms):
    """Whisper's initial prompt: the context sentence, then the terms. None if both are empty."""
    parts = []
    if context.strip():
        parts.append(context.strip().rstrip(".") + ".")
    if terms:
        parts.append(", ".join(terms) + ".")
    return " ".join(parts) or None
