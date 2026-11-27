"""The caption window: borderless, always on top. The whole session's captions in a scrollable box (mouse wheel; End jumps to
the latest line), Thai large with the English small underneath, and the line still being spoken in yellow at the bottom.
Drag the top or bottom strip to move; drag the right edge, bottom edge or corner to resize; right-click for the menu."""


class Window:
    BG, TH_FG, EN_FG, PART_FG = "#111418", "#FFFFFF", "#9FB0C2", "#C9B26B"

    def __init__(self, ui_q, cap, rec, audio, settings):
        import tkinter as tk
        self.tk, self.ui_q, self.cap, self.rec, self.audio, self.s = tk, ui_q, cap, rec, audio, settings
        self.size, self.show_en, self.compact, self.lines = settings.font_size, True, False, []
        r = self.root = tk.Tk()
        r.title("Live captions")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", settings.opacity)
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        self.w, self.h = int(sw * 0.62), int(sh * 0.24)
        r.geometry(f"{self.w}x{self.h}+{(sw - self.w) // 2}+{int(sh * 0.70)}")
        r.configure(bg=self.BG)
        self.status = tk.Label(r, text="starting…", fg="#8A96A3", bg=self.BG, font=(settings.latin_font, 9), anchor="w")
        self.status.pack(side="top", fill="x", padx=12, pady=(6, 0))
        self.partial = tk.Label(r, text="", fg=self.PART_FG, bg=self.BG, anchor="w", justify="left")
        self.partial.pack(side="bottom", fill="x", padx=12, pady=(0, 10))
        self.text = tk.Text(r, bg=self.BG, fg=self.TH_FG, bd=0, highlightthickness=0, wrap="word", cursor="arrow",
                            padx=0, pady=2, insertwidth=0, takefocus=0, selectbackground="#2C5183")
        self.text.pack(side="top", fill="both", expand=True, padx=(12, 14), pady=(2, 4))
        for w in (self.status, self.partial):
            self._drag(w)
        # resize handles: right edge, bottom edge, bottom-right corner
        for name, cur, place in [("e", "sb_h_double_arrow", dict(relx=1.0, rely=0, relheight=1.0, width=7, anchor="ne")),
                                 ("s", "sb_v_double_arrow", dict(relx=0, rely=1.0, relwidth=1.0, height=7, anchor="sw")),
                                 ("se", "size_nw_se", dict(relx=1.0, rely=1.0, width=16, height=16, anchor="se"))]:
            g = tk.Frame(r, bg="#3A4350" if name == "se" else self.BG, cursor=cur)
            g.place(**place)
            g.bind("<Button-1>", self._grab)
            g.bind("<B1-Motion>", lambda e, n=name: self._resize(e, n))
        keys = {"r": self.toggle_rec, "m": self.toggle_mic, "t": self.toggle_en, "plus": lambda: self.font(2),
                "equal": lambda: self.font(2), "minus": lambda: self.font(-2), "space": self.toggle_pause,
                "c": self.toggle_compact, "Escape": self.quit, "End": self.to_end}
        for k, f in keys.items():
            for w in (r, self.text):
                w.bind(f"<{k}>" if len(k) > 1 else k, lambda e, f=f: self._key(f))
                if len(k) == 1:
                    w.bind(k.upper(), lambda e, f=f: self._key(f))
        self.text.bind("<Key>", self._readonly)  # text can be selected and copied (Ctrl+C), not typed into
        r.bind_all("<MouseWheel>", lambda e: self.text.yview_scroll(int(-e.delta / 40), "units"))
        m = self.menu = tk.Menu(r, tearoff=0)
        for lab, f in [("Record on/off (R)", self.toggle_rec), ("Caption my mic (M)", self.toggle_mic),
                       ("Show English (T)", self.toggle_en), ("Bigger (+)", lambda: self.font(2)),
                       ("Smaller (-)", lambda: self.font(-2)), ("Pause (Space)", self.toggle_pause),
                       ("Compact (C)", self.toggle_compact), ("Jump to latest (End)", self.to_end), ("Quit (Esc)", self.quit)]:
            m.add_command(label=lab, command=f)
        for w in (r, self.text, self.status, self.partial):
            w.bind("<Button-3>", lambda e: m.tk_popup(e.x_root, e.y_root))
        self.st, self.lag = "starting…", None
        self.fonts()
        r.after(100, self.poll)
        r.after(1000, self.tick)

    def _key(self, f):
        f()
        return "break"

    @staticmethod
    def _readonly(e):
        if (e.state & 0x4) and e.keysym.lower() in ("c", "a"):  # Ctrl+C, Ctrl+A
            return None
        if e.keysym in ("Prior", "Next", "Up", "Down", "Home"):
            return None
        return "break"

    # -- moving and resizing
    def _drag(self, w):
        def press(e):
            self.dx, self.dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()
            self.root.focus_force()
        w.bind("<Button-1>", press)
        w.bind("<B1-Motion>", lambda e: self.root.geometry(f"+{e.x_root - self.dx}+{e.y_root - self.dy}"))

    def _grab(self, e):
        self.g0 = (e.x_root, e.y_root, self.root.winfo_width(), self.root.winfo_height())

    def _resize(self, e, edge):
        x0, y0, w0, h0 = self.g0
        if "e" in edge:
            self.w = max(320, w0 + e.x_root - x0)
        if "s" in edge:
            self.h = max(110, h0 + e.y_root - y0)
        self.root.geometry(f"{self.w}x{self.h}")
        self.partial.configure(wraplength=self.w - 30)

    # -- captions
    def fonts(self):
        self.text.tag_configure("th", font=(self.s.thai_font, self.size), foreground=self.TH_FG, spacing1=4)
        self.text.tag_configure("en", font=(self.s.latin_font, max(10, self.size - 8)), foreground=self.EN_FG, spacing3=6,
                                elide=not self.show_en)
        self.partial.configure(font=(self.s.latin_font, max(10, self.size - 6), "italic"), wraplength=self.w - 30)

    def at_end(self):
        return self.text.yview()[1] >= 0.999

    def add_line(self, who, en, th):
        follow = self.at_end()
        tag = "" if who == "them" else "(you) "
        if self.lines:
            self.text.insert("end", "\n")
        self.text.insert("end", tag + th + "\n", "th")
        self.text.insert("end", tag + en, "en")
        self.lines.append((who, en, th))
        if follow:
            self.text.see("end")

    def to_end(self):
        self.text.see("end")

    def poll(self):
        while not self.ui_q.empty():
            m = self.ui_q.get()
            if m[0] == "status":
                self.st = m[1]
            elif m[0] == "final":
                self.add_line(*m[1:4])
                self.lag = m[4]
            elif m[0] == "partial" and (m[1] == "them" or self.cap.mic_captions):
                self.partial.configure(text=m[2])
        self.root.after(100, self.poll)

    def tick(self):
        s = self.rec.elapsed()
        bits = [self.st, f"● REC {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}" if self.rec.on else "not recording (R to record)"]
        if self.cap.paused:
            bits.append("PAUSED")
        if self.cap.mic_captions:
            bits.append("mic captions on")
        if self.lines and not self.at_end():
            bits.append("scrolled back · End = latest")
        elif self.lag is not None:
            bits.append(f"Thai {self.lag:.1f}s after the pause")
        self.status.configure(text="   ·   ".join(bits), fg="#E06C5B" if self.rec.on else "#8A96A3")
        self.root.after(1000, self.tick)

    def toggle_rec(self):
        self.st = self.rec.toggle()

    def toggle_mic(self):
        self.cap.mic_captions = not self.cap.mic_captions

    def toggle_en(self):
        self.show_en = not self.show_en
        self.fonts()

    def toggle_pause(self):
        self.cap.paused = not self.cap.paused

    def toggle_compact(self):
        """Compact: Thai only, window just tall enough for about two lines; press again to go back."""
        self.compact = not self.compact
        if self.compact:
            self._saved = (self.h, self.show_en)
            self.show_en = False
            self.h = int(self.size * 2 * 2.2 + 70)
        else:
            self.h, self.show_en = self._saved
        self.fonts()
        self.root.geometry(f"{self.w}x{self.h}")
        self.to_end()

    def font(self, d):
        self.size = min(40, max(12, self.size + d))
        self.fonts()

    def quit(self):
        if self.rec.on:
            print("[rec]", self.rec.toggle(), flush=True)
        self.audio.stop.set()
        self.root.destroy()
