"""Speech to text (faster-whisper) and English to Thai (NLLB-200), fed from Audio's queues; results go to the window's queue as
("partial", who, text), ("final", who, en, th, seconds_after_pause) and ("status", text)."""
import queue
import re
import threading
import time

import numpy as np

from .config import JUNK, SR


class Captioner:
    def __init__(self, ui_q, rec, settings):
        self.ui_q, self.rec, self.s = ui_q, rec, settings
        self.paused, self.mic_captions = False, False
        self.prompt = settings.prompt()
        self.tq = queue.Queue()

    def load(self):
        s = self.s
        dev = s.device
        if dev == "cuda":
            import torch  # loads torch's CUDA DLLs (cuBLAS, cuDNN) first, which CTranslate2 also needs on Windows
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available: check the NVIDIA driver and that torch is a CUDA build (see README)")
        from faster_whisper import WhisperModel
        self.ui_q.put(("status", "loading Whisper…"))
        self.asr = WhisperModel(s.whisper_model(), device=dev, compute_type=s.compute())
        self.ui_q.put(("status", "loading Thai translation…"))
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        name = s.nllb_model()
        self.tok = AutoTokenizer.from_pretrained(name, src_lang="eng_Latn")
        dtype = torch.float16 if dev == "cuda" else torch.float32
        self.mt = AutoModelForSeq2SeqLM.from_pretrained(name, dtype=dtype).to(dev).eval()
        self.th_id = self.tok.convert_tokens_to_ids("tha_Thai")
        self.asr.transcribe(np.zeros(SR, np.float32), language="en")  # warm up
        self.ui_q.put(("status", "ready"))

    def translate(self, en):
        import torch
        # One sentence at a time: NLLB tends to drop a sentence when given two at once.
        parts = [p for p in re.split(r"(?<=[.?!])\s+", en) if p.strip()]
        with torch.inference_mode():
            x = self.tok(parts, return_tensors="pt", padding=True, truncation=True, max_length=200).to(self.s.device)
            y = self.mt.generate(**x, forced_bos_token_id=self.th_id, num_beams=2, max_new_tokens=200)
        return " ".join(self.tok.batch_decode(y, skip_special_tokens=True))

    def _text(self, audio, beam):
        segs, _ = self.asr.transcribe(audio, language="en", beam_size=beam, condition_on_previous_text=False,
                                      initial_prompt=self.prompt, vad_filter=False, without_timestamps=True,
                                      no_speech_threshold=0.6)
        t = " ".join(seg.text.strip() for seg in segs if seg.no_speech_prob < 0.8).strip()
        return "" if t.lower() in JUNK else t

    def _translator(self):
        while True:
            who, en, t_end = self.tq.get()
            th = self.translate(en)
            self.ui_q.put(("final", who, en, th, time.time() - t_end))
            self.rec.line(who, en, th)

    def run(self, audio):
        """Every 0.4 s: take the new audio, show a quick (beam 1) partial of the line so far, and finish the line with
        beam 5 + translation once there is a pause (settings.pause) or the line is too long (settings.max_len)."""
        pause, max_len = self.s.pause, self.s.max_len
        threading.Thread(target=self._translator, daemon=True).start()
        streams = {"them": audio.q_them, "me": audio.q_me}
        cur = {"them": np.zeros(0, np.float32), "me": np.zeros(0, np.float32)}
        last_voice = {"them": -1, "me": -1}
        frame = int(0.05 * SR)
        while True:
            time.sleep(0.4)
            for who, q in streams.items():
                new = []
                while not q.empty():
                    new.append(q.get())
                if not new:
                    continue
                x = np.concatenate(new)
                self.rec.add(who, x)
                if self.paused or (who == "me" and not self.mic_captions):
                    cur[who] = np.zeros(0, np.float32)
                    continue
                base = len(cur[who])
                cur[who] = np.concatenate([cur[who], x])
                n = len(x) // frame
                if n:
                    rms = np.sqrt((x[:n * frame].reshape(n, frame) ** 2).mean(1))
                    loud = np.nonzero(rms > 0.01)[0]
                    if len(loud):
                        last_voice[who] = base + (loud[-1] + 1) * frame
            for who in ("them", "me"):
                a = cur[who]
                if len(a) < SR // 2:
                    continue
                if last_voice[who] < 0:  # nothing heard yet: keep only the last 0.3 s
                    cur[who] = a[-int(0.3 * SR):]
                    continue
                silence = (len(a) - last_voice[who]) / SR
                if silence > pause or len(a) > max_len * SR:
                    cut = len(a) if silence > pause else quiet_cut(a)
                    t0 = time.time()
                    en = self._text(a[:cut], 5)
                    if en:
                        self.tq.put((who, en, t0))
                    self.ui_q.put(("partial", who, ""))
                    cur[who] = a[cut:]
                    last_voice[who] = -1 if silence > pause else max(-1, last_voice[who] - cut)
                else:
                    self.ui_q.put(("partial", who, self._text(a, 1)))


def quiet_cut(a):
    """Where to cut a long stretch: after the quietest 0.15 s in its last 2.5 s, so a sentence is less likely to be split mid-word."""
    f = int(0.15 * SR)
    tail = a[-int(2.5 * SR):]
    n = len(tail) // f
    rms = np.sqrt((tail[:n * f].reshape(n, f) ** 2).mean(1))
    return len(a) - len(tail) + (int(rms.argmin()) + 1) * f
