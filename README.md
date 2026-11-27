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
- **About 13 GB of disk:** about 6 GB for the models and about 7 GB for Python and PyTorch.
  - The download is about 10 GB.
  - The app installs Python by itself. From the source code you need Python 3.11, most easily through [uv](https://docs.astral.sh/uv/).
- **Tested versions:** Python 3.11, torch 2.8.0+cu128, faster-whisper 1.2.1, transformers 4.57.6. `uv.lock` installs exactly these.
- **[ffmpeg](https://ffmpeg.org/) on PATH**, needed only for rehearsal and the tests. Install it with `winget install Gyan.FFmpeg`.

## Install

### The app (recommended)

1. Download `LiveCaptions-<version>-win64.zip` from the [Releases](../../releases) page. The zip is about 25 MB.
2. Extract it to a folder of your own, for example `Documents\LiveCaptions`.
   - Right-click the zip and choose **Extract All**.
   - Don't run it from inside the zip, and don't put it in `Program Files`.
3. Double-click **`Live Captions.exe`**. The first time, a setup window opens:
   - It installs Python, the packages and the models, about 10 GB in 10–30 minutes.
   - It checks the graphics card.
   - It can add Live Captions to the Start menu and the desktop.
   - After that, Live Captions opens straight away.

Notes:

- **Setup stopped?** Run it again; the parts already done are kept.
- **Repair:** `Live Captions.exe --setup` runs the setup again.
- **New version:** extract it to a new folder. To skip downloading the models again, copy the `models` folder from the old one first.
- **Rehearsal:** drop an audio or video file on `Live Captions.exe` to rehearse with it.
- **Errors** are written to `logs\live-captions.log`.

### From the source code

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it. Run this in PowerShell:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Double-click **`setup.bat`**. It does three things:
   - installs the packages into `.venv`, with the CUDA build of PyTorch (`uv sync`)
   - checks that the GPU can be used
   - downloads the models
3. Double-click **`start_live_captions.bat`**.

`setup.bat` can be run again safely; it skips what is already there.

### By hand

With uv, run this in the repo folder:

```powershell
uv sync
```

This creates `.venv` with the CUDA 12.8 build of PyTorch. The launch scripts find `.venv` by themselves.

With pip instead:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements.txt
```

You can also use an environment you already have. It needs faster-whisper, transformers and a CUDA build of torch.
Create `local.bat` in the repo folder (git ignores it) with:

```bat
set "LIVE_CAPTIONS_PYTHON=C:\path\to\your\env\Scripts\python.exe"
```

To check the GPU, run the following. It should print `True` and the name of your GPU.

```powershell
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## Download the models

`setup.bat` does this for you. To do it on its own, double-click `download_models.bat`, or run
`.venv\Scripts\python -m live_captions.download`. It downloads about 5.5 GB:

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

- **`terms.example.txt` → `terms.txt`** (`setup.bat` makes it for you):
  - List names, acronyms and jargon you expect to hear in the call.
  - Whisper spells these correctly much more often when they are listed.
  - Change the list for each meeting, and keep it under about 100 terms.
- **`config.example.toml` → `config.toml`:**
  - model names or folders
  - device
  - pause length
  - where recordings go
  - fonts
  - hiding from screen sharing

The window remembers its size, position, text size, opacity, pin and English on/off by itself. It keeps them in
`%APPDATA%\live-captions\window.json`.

Command-line options override `config.toml`. Run `python -m live_captions --help` to see them.

## Use

| What | How |
|---|---|
| Live, in a call | Double-click `start_live_captions.bat`. The models take 15–30 s to load. The light in the top-left turns green when it is ready. |
| Rehearse without a call | Drag an audio or video file onto `rehearse.bat`. It plays the file and captions it. You can also run `rehearse.bat <file> [start seconds]`. |
| Rehearse while presenting | Start a PowerPoint slideshow, then run `rehearse.bat`. Check whether the captions cover your slides and whether you can read them in time. |

### The window

- **Header:**
  - **Status light:** amber while loading, green when live, grey when paused, red on an error.
  - **Level meter:** moves when the call has sound, so you can tell at a glance that the tool hears the call.
  - **Red `● REC` timer:** shows while recording.
- **Buttons:** they appear in the header when the mouse is over the window, from left to right:
  - **EN:** show or hide the English
  - **mic:** caption your microphone too
  - **text smaller / bigger**
  - **compact:** Thai only, two lines
  - **pause**
  - **record:** click twice to start
  - **pin:** keep the window on top of other windows, or let them cover it
  - **help**
  - **minimize:** to the taskbar; click its taskbar button to bring it back
  - **close**

  Hover over a button to see what it does in the header.
- **Captions:**
  - The newest line is bright and older lines are dimmed.
  - Your own lines (with **M**) are blue and start with "You ·".
- **Scroll back:**
  - Use the mouse wheel. The window keeps every caption since it started.
  - While you are scrolled back, new lines do not pull the view down.
  - Click **↓ Latest** or press **End** to go back to the newest line.
- **Move:** drag the header or the yellow line.
- **Resize:** drag the right edge, the bottom edge or the dotted bottom-right corner.
- **Copy:** select text with the mouse, then press Ctrl+C.
- **Right-click** opens the menu. Besides every command above, it has:
  - opacity
  - hiding from screen sharing
  - resetting the size and position

### Keys

Click the caption window first. **F1** or **?** shows these in the window.

| Key | Action |
|---|---|
| **R** | Start or stop recording. To start, press it **twice**; stopping takes one press. |
| **T** | Show or hide the English |
| **+ / -** | Bigger or smaller text |
| **C** | Compact mode: Thai only, about 2 lines; press again to go back |
| **End** | Jump to the latest line |
| **Space** | Pause captions |
| **M** | Caption your own microphone too (off by default) |
| **P** | Keep on top of other windows, or not (pin / unpin) |
| **F1** or **?** | Keys and controls |
| **Esc** | Quit (press it **twice**, so a stray key press does not close the captions mid-call) |

## ⚠️ Screen sharing

- **The caption window is hidden from screen sharing and screenshots by default.**
  - The others in the call do not see it, even if you share your whole screen.
  - This uses the Windows setting `WDA_EXCLUDEFROMCAPTURE`, which needs Windows 10 version 2004 or newer.
  - If it is not available, a message in the header says so.
  - You can switch it off in the right-click menu, or with `hide_from_capture = false` in `config.toml`.
- **Still share only the PowerPoint window, not the whole screen, when you can.** It is the safest choice.
  - Try a test share once with your meeting app before an important call, because not every app has been tested.
  - With Zoom, sharing a single window does not show the caption window.
- If you have two screens, you can also move the caption window to the screen you are not sharing.

## Recording

- **Captions alone save nothing.**
  - Recording starts only after you press **R twice**. The first press shows a reminder to make sure everyone has agreed.
  - It stops when you press R again or quit.
- **Ask everyone for consent before you record.**
  - Recording other people without their consent may be illegal where you or they are, and it is unfair to them either way.
  - The tool does not make Zoom or Teams show that you are recording, so you must tell people yourself.
- While it records, a red `● REC` timer shows in the header. When you stop, the header shows where the files went.
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
  - Watch the level meter in the header. If it does not move while people talk, the tool does not hear the call.
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
| `setup.bat` | One-click setup from the source code: packages, GPU check, models, `terms.txt` |
| `launcher/Launcher.cs` | `Live Captions.exe`: first-run setup window, then starts the app without a console |
| `tools/build_release.ps1` | Builds the release zip into `dist\` |
| `tools/make_icon.py` | Draws `live_captions/assets/app.ico` |
| `.github/workflows/release.yml` | Builds the zip on GitHub; pushing a tag like `v0.2.0` publishes it as a release |
| `start_live_captions.bat`, `rehearse.bat`, `download_models.bat` | Launchers. `scripts\find_python.bat` picks the Python. |
| `config.example.toml`, `terms.example.txt` | Examples to copy to `config.toml` and `terms.txt`. |
| `tests/test_basics.py`, `tests/test_window_logic.py` | Quick checks without a GPU or models: `python -m unittest discover -s tests` |
| `tests/test_pipeline.py` | Headless check of the whole pipeline on an audio file, with timings: `python -X utf8 tests/test_pipeline.py <file>` |
| `tests/test_window.py` | Window check with screenshots: scrolling back and resizing |
| `tests/make_sample_audio.ps1` | Makes `tests\sample.wav`, an English sample from Windows text-to-speech |

## Making a release

1. Update the version in `pyproject.toml` and `live_captions/__init__.py`, then commit.
2. Tag and push:

   ```powershell
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. The **Release** workflow builds `LiveCaptions-v0.2.0-win64.zip` and publishes it on the Releases page.

To build the zip on your own computer:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_release.ps1 -Version v0.2.0
```

## License

- **Live Captions** (this code) is under the [MIT License](LICENSE).
- **The models** are not part of this repository or the release zip. Setup downloads them from Hugging Face, and each
  has its own license:
  - **Whisper large-v3** (OpenAI) and the **faster-whisper** conversion: MIT.
  - **NLLB-200** (Meta): [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), **non-commercial use only**.
    For commercial use, swap in a translation model whose license allows it (`nllb` in `config.toml`).
