# Live captions (English → Thai)

Live captions for online meetings and interviews. The tool listens to what comes out of your computer's speakers, so it
hears everyone in a Zoom, Teams or Meet call. It shows the captions in a small window that stays on top of your other windows:

- **Thai** (machine translation) in large white text, with the **English** in small grey text underneath
- the sentence still being spoken in **yellow** at the bottom

Everything runs on your own computer, on the GPU. No audio or text is sent anywhere.
- **Speech to text:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with Whisper large-v3
- **English to Thai:** Meta's [NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M), the distilled 600M model

ภาษาไทย: [README_TH.md](README_TH.md)

## Requirements

- **Windows 10 or 11.** Audio comes from WASAPI loopback, which is Windows-only.
- **An NVIDIA GPU with CUDA.**
  - Tested on an RTX 4070 (12 GB). It uses about 1.3–3 GB of GPU memory, so a 6 GB card should be enough.
  - You need a recent NVIDIA driver: version 570 or newer, for the CUDA 12.8 build of PyTorch.
  - You do not need to install the CUDA toolkit. PyTorch and CTranslate2 bring the CUDA libraries they need.
  - The CPU works only for testing (`--device cpu`). It is far too slow for live captions with large-v3.
- **Python 3.11 or newer.** [uv](https://docs.astral.sh/uv/) is the easiest way to get it.
- **About 6 GB of disk** for the models, plus about 5 GB for PyTorch.
- **Tested versions:** Python 3.11, torch 2.8.0+cu128, faster-whisper 1.2.1, transformers 4.57. `uv.lock` pins newer
  versions that resolve cleanly but were not tested live.
- **[ffmpeg](https://ffmpeg.org/) on PATH**, needed only for rehearsal and the tests. Install it with `winget install Gyan.FFmpeg`.

## Install

### With uv (recommended)

Run this in the repo folder:

```powershell
uv sync
```

This creates `.venv` with the CUDA 12.8 build of PyTorch. The launch scripts find `.venv` by themselves.

### With pip

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements.txt
```

### Using an existing environment

You can use an environment you already have. It needs faster-whisper, transformers and a CUDA build of torch. Create
`local.bat` in the repo folder (git ignores it) with:

```bat
set "LIVE_CAPTIONS_PYTHON=C:\path\to\your\env\Scripts\python.exe"
```

### Check the GPU

```powershell
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

This should print `True` and the name of your GPU.

## Download the models

Double-click `download_models.bat`, or run `.venv\Scripts\python -m live_captions.download`. It downloads about 5.5 GB:

- Whisper large-v3 into `models\faster-whisper-large-v3`
- NLLB-200 600M into `models\nllb-200-distilled-600M`

The tool finds both folders by itself.

> **Why not the normal Hugging Face cache?** The cache uses symbolic links. On Windows without admin rights or
> Developer Mode, creating them can fail with `OSError: [WinError 1314] A required privilege is not held by the client`.
> The download script avoids this: it saves plain files with `local_dir`. If you already have the models somewhere,
> point `config.toml` at those folders instead.

To try a smaller Whisper on a smaller GPU: `download_models.bat --whisper small.en`, then set `whisper = "small.en"` in `config.toml`.

## Settings

All settings are optional. To change them, copy these files (git ignores the copies):

- **`config.example.toml` → `config.toml`:**
  - model names or folders
  - device
  - pause length
  - where recordings go
  - fonts and opacity
- **`terms.example.txt` → `terms.txt`:** names, acronyms and jargon you expect to hear in the call. Whisper spells these
  correctly much more often when they are listed. Change the list for each meeting; keep it under about 100 terms.

Command-line options override `config.toml`. Run `python -m live_captions --help` to see them.

## Use

| What | How |
|---|---|
| Live, in a call | Double-click `start_live_captions.bat`. The models take 15–30 s to load; wait until the top bar says `ready`. |
| Rehearse without a call | Drag an audio or video file onto `rehearse.bat`. It plays the file and captions it. You can also run `rehearse.bat <file> [start seconds]`. |
| Rehearse while presenting | Start a PowerPoint slideshow, then run `rehearse.bat`. Check whether the captions cover your slides and whether you can read them in time. |

### Mouse

- **Scroll back:** use the mouse wheel on the window. The window keeps every caption since it started.
  - While you are scrolled back, new lines do not pull the view down, and the top bar says `scrolled back · End = latest`.
  - Press **End** to jump back to the latest line.
- **Resize:**
  - drag the right edge for width
  - drag the bottom edge for height
  - drag the bottom-right corner (the small grey square) for both
- **Move:** drag the top bar (small grey text) or the yellow line at the bottom.
- **Copy:** select text with the mouse, then press Ctrl+C.
- **Right-click:** opens a menu with every command.

### Keys

Click the caption window first.

| Key | Action |
|---|---|
| **R** | Start or stop recording |
| **T** | Show or hide the English |
| **+ / -** | Bigger or smaller text |
| **C** | Compact mode: Thai only, about 2 lines; press again to go back |
| **End** | Jump to the latest line |
| **Space** | Pause captions |
| **M** | Caption your own microphone too (off by default; your lines start with "(you)") |
| **Esc** | Quit |

## ⚠️ Screen sharing in Zoom

- **Share only the PowerPoint window, not your whole screen.** If you share the whole screen, everyone in the call sees your captions.
  - Sharing a single window does not show the caption window. This was tested with Zoom.
- If you have two screens, you can also move the caption window to the screen you are not sharing.

## Recording

- **Captions alone save nothing.** The tool records only after you press **R**, and stops when you press R again or quit.
- **Ask everyone for consent before you press R.**
  - Recording other people without their consent may be illegal where you or they are, and it is unfair to them either way.
  - The tool does not make Zoom or Teams show that you are recording, so you must tell people yourself.
- While it records, the top bar turns red and shows `● REC` and the time.
- Each recording goes to `sessions\<date-time>\`:
  - **`audio.wav`:** 16 kHz stereo, with **left = the other side** (the speaker output) and **right = your microphone**
  - **`captions.txt`:** the English and Thai lines, with times from the start of the recording
- `sessions\` is in `.gitignore`, so recordings are never committed.

## Performance (RTX 4070, Whisper large-v3)

- **English:** the yellow line appears about 0.3 s after the words are spoken.
- **Thai:** appears about 0.5–1 s after the speaker pauses.
- **Line length:** a line ends after a 0.45 s pause, or at 8 s of speech, cut at the quietest point.
- **GPU memory:** about 1.3–3 GB.

## Limitations

- **The Thai is machine translation.**
  - It gets the gist across, but it is often stiff.
  - Some terms, such as product names or official titles, come out word for word and lose their meaning.
  - Use it to follow the conversation, never as a quote or a record.
- **Overlapping speech:** when two people talk at once, their words end up on one line.
- **No speaker names:** captions only tell "them" (the speaker output) from "you" (the microphone, with **M**).
- **English in only:** the Thai side is a translation, so the tool does not understand Thai speech.
- **Audio devices:**
  - It uses the Windows default output and input devices.
  - If you switch headsets during a call, restart the tool.

## Troubleshooting

- **No captions:**
  - Check the console window for a line like `[audio] speaker output: …`.
  - The call's audio must play through the Windows default output device.
- **`CUDA is not available`:**
  - Update the NVIDIA driver.
  - Check that torch is a CUDA build. It should print a version ending in `+cu128`:

    ```powershell
    .venv\Scripts\python -c "import torch; print(torch.__version__)"
    ```
- **`WinError 1314` while loading a model:** see [Download the models](#download-the-models).
- **Slow or stuttering:** close other programs that use the GPU heavily, such as games or OBS with the GPU encoder.

## Files

| Path | What |
|---|---|
| `live_captions/` | The program. `cli.py` is the entry point. The other modules are `audio.py`, `captioner.py` (Whisper + NLLB), `recorder.py`, `window.py` and `config.py`. |
| `start_live_captions.bat`, `rehearse.bat`, `download_models.bat` | Launchers. `scripts\find_python.bat` picks the Python. |
| `config.example.toml`, `terms.example.txt` | Examples to copy to `config.toml` and `terms.txt`. |
| `tests/test_basics.py` | Quick checks without a GPU: `python -m unittest discover -s tests` |
| `tests/test_pipeline.py` | Headless check of the whole pipeline on an audio file, with timings: `python -X utf8 tests/test_pipeline.py <file>` |
| `tests/test_window.py` | Window check with screenshots: scrolling back and resizing |
| `tests/make_sample_audio.ps1` | Makes `tests\sample.wav`, an English sample from Windows text-to-speech |
