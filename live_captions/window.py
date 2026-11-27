"""The caption window: borderless, always on top, hidden from screen sharing.

Layout, top to bottom:
- header: status light and text, speaker level meter, REC timer; the buttons appear while the mouse is over the window
- captions: the whole session, newest line bright and older lines dimmed, Thai large with the English small underneath
- the line still being spoken, in yellow

Drag the header or the yellow line to move; drag the right edge, bottom edge or corner to resize; right-click for the menu.
Size, position, text size and the English on/off are remembered between runs."""
import ctypes
import json
import math
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

C = dict(
    bg="#0F1216", border="#2A313B", th="#F4F6F8", en="#9AA6B2", th_old="#A9B3BD", en_old="#677380",
    me="#9CC2FF", partial="#E8C872", muted="#7D8995", faint="#3A424D", hover="#222831", pill="#1B2028",
    ok="#3FB97F", warn="#E5A84B", err="#F2615D", sel="#2C5183",
)
ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
ICONS = {  # Segoe Fluent Icons / MDL2 code points, with a plain-text fallback
    "rec": ("", "●"), "mic": ("", "Mic"), "smaller": ("", "A-"), "bigger": ("", "A+"),
    "compact": ("", "▭"), "expand": ("", "▢"), "pause": ("", "II"), "play": ("", "▶"),
    "help": ("", "?"), "close": ("", "×"),
}
HELP = [
    ("R", "Start or stop recording (press twice to start)"),
    ("M", "Caption my microphone too"),
    ("T", "Show or hide the English"),
    ("+  /  −", "Bigger or smaller text"),
    ("C", "Compact: Thai only, two lines"),
    ("Space", "Pause captions"),
    ("End", "Jump to the latest line"),
    ("Mouse wheel", "Scroll back through the session"),
    ("Drag", "Header or yellow line: move · edges and corner: resize"),
    ("Right-click", "Menu: opacity, screen-share hiding, reset position"),
    ("Esc  Esc", "Quit (press twice)"),
]


def default_state_file():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "live-captions", "window.json")


def _dpi_aware():
    """Sharp text on high-DPI screens (otherwise Windows stretches the window and the text is blurry)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


class Window:
    def __init__(self, ui_q, cap, rec, audio, settings, hide_from_capture=None, state_file=None):
        self.ui_q, self.cap, self.rec, self.audio, self.s = ui_q, cap, rec, audio, settings
        self.state_file = state_file or default_state_file()
        self.hide_capture = settings.hide_from_capture if hide_from_capture is None else hide_from_capture
        st = self._load_state()
        self.size = int(st.get("size", settings.font_size))
        self.show_en = bool(st.get("show_en", True))
        self.opacity = float(st.get("opacity", settings.opacity))
        self.compact, self.lines, self.help_on = False, [], False
        self.state, self.state_msg, self.error = "loading", "Starting…", None
        self._toast, self._tip, self._armed = None, None, {}
        self._hover, self._level = False, 0.0

        _dpi_aware()
        r = self.root = tk.Tk()
        r.title("Live captions")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", self.opacity)
        r.configure(bg=C["border"])
        self.k = r.winfo_fpixels("1i") / 96.0
        fams = set(tkfont.families(r))
        self.icon_font = next((f for f in ICON_FONTS if f in fams), None)
        self.thai = settings.thai_font if settings.thai_font in fams else "Tahoma"
        self.latin = settings.latin_font if settings.latin_font in fams else "Segoe UI"

        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        self.w = int(st.get("w", min(sw * 0.62, self.px(1500))))
        self.h = int(st.get("h", sh * 0.24))
        x, y = int(st.get("x", (sw - self.w) // 2)), int(st.get("y", sh * 0.70))
        x, y = self._on_screen(x, y)
        r.geometry(f"{self.w}x{self.h}+{x}+{y}")

        frame = self.frame = tk.Frame(r, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        self._build_header(frame)
        self.partial = tk.Label(frame, text="", fg=C["partial"], bg=C["bg"], anchor="w", justify="left")
        self.partial.pack(side="bottom", fill="x", padx=self.px(16), pady=(0, self.px(10)))
        self.body = tk.Frame(frame, bg=C["bg"])
        self.body.pack(side="top", fill="both", expand=True)
        self.text = tk.Text(self.body, bg=C["bg"], fg=C["th"], bd=0, highlightthickness=0, wrap="word", cursor="arrow",
                            padx=0, pady=self.px(2), insertwidth=0, takefocus=0, selectbackground=C["sel"])
        self.text.pack(fill="both", expand=True, padx=(self.px(16), self.px(18)), pady=(self.px(2), self.px(4)))
        self.placeholder = tk.Label(self.body, text="", fg=C["muted"], bg=C["bg"], justify="center")
        self.latest = tk.Label(self.body, text="↓  Latest", fg=C["th"], bg=C["pill"], cursor="hand2", padx=self.px(10),
                               pady=self.px(3))
        self.latest.bind("<Button-1>", lambda e: self.to_end())
        self._build_help()
        for w in (self.partial, self.placeholder):
            self._drag(w)
        self._build_grips()
        self._bind_keys()
        self._build_menu()
        self.fonts()
        self._render_placeholder()
        r.after(50, self._native)
        r.after(100, self.poll)
        r.after(120, self.fast_tick)
        r.after(1000, self.tick)

    # ------------------------------------------------------------------ building
    def px(self, n):
        return int(round(n * self.k))

    def _build_header(self, parent):
        h = self.head = tk.Frame(parent, bg=C["bg"], height=self.px(34))
        h.pack(side="top", fill="x", padx=(self.px(12), self.px(6)), pady=(self.px(4), 0))
        h.grid_propagate(False)
        h.columnconfigure(1, weight=1)
        h.rowconfigure(0, weight=1)
        d = self.px(10)
        self.dot = tk.Canvas(h, width=d, height=d, bg=C["bg"], highlightthickness=0)
        self.dot_id = self.dot.create_oval(1, 1, d - 1, d - 1, fill=C["warn"], outline="")
        self.dot.grid(row=0, column=0, padx=(0, self.px(8)))
        self.status = tk.Label(h, text="", fg=C["muted"], bg=C["bg"], anchor="w")
        self.status.grid(row=0, column=1, sticky="ew")
        self.meter = tk.Canvas(h, width=self.px(46), height=self.px(14), bg=C["bg"], highlightthickness=0)
        self.meter.grid(row=0, column=2, padx=(self.px(8), self.px(6)))
        self._tooltip(self.meter, "Speaker output level: it moves when the call has sound")
        self.rec_pill = tk.Label(h, text="", fg="#FFFFFF", bg=C["err"], padx=self.px(8), pady=self.px(1), cursor="hand2")
        self.rec_pill.bind("<Button-1>", lambda e: self.toggle_rec())
        self._tooltip(self.rec_pill, "Recording. Click or press R to stop and save")
        self.btns = tk.Frame(h, bg=C["bg"])
        self.buttons = {}
        for name, tip, fn in [
            ("en", "Show or hide the English (T)", self.toggle_en),
            ("mic", "Caption my microphone too (M)", self.toggle_mic),
            ("smaller", "Smaller text (−)", lambda: self.font(-2)),
            ("bigger", "Bigger text (+)", lambda: self.font(2)),
            ("compact", "Compact: Thai only (C)", self.toggle_compact),
            ("pause", "Pause captions (Space)", self.toggle_pause),
            ("rec", "Record (R, press twice to start)", self.toggle_rec),
            ("help", "Keys and controls (F1 or ?)", self.toggle_help),
            ("close", "Quit", self.quit),
        ]:
            b = tk.Label(self.btns, bg=C["bg"], fg=C["muted"], cursor="hand2", width=3, pady=self.px(2))
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, fn=fn: (fn(), "break")[1])
            b.bind("<Enter>", lambda e, b=b, tip=tip, n=name: (b.configure(bg=C["err"] if n == "close" else C["hover"]),
                                                              self._set_tip(tip)))
            b.bind("<Leave>", lambda e, b=b: (b.configure(bg=C["bg"]), self._set_tip(None)))
            self.buttons[name] = b
        for w in (h, self.status, self.dot):
            self._drag(w)

    def _icon(self, name, size=11):
        glyph, plain = ICONS[name]
        if self.icon_font:
            return glyph, (self.icon_font, size)
        return plain, (self.latin, size - 1, "bold")

    def _paint_buttons(self):
        on = {"en": self.show_en, "mic": self.cap.mic_captions, "pause": self.cap.paused, "rec": self.rec.on}
        for name, b in self.buttons.items():
            if name == "en":
                b.configure(text="EN", font=(self.latin, 9, "bold"))
            else:
                icon = {"compact": "expand" if self.compact else "compact", "pause": "play" if self.cap.paused else "pause"}.get(name, name)
                txt, f = self._icon(icon, 10 if name in ("close", "help") else 11)
                b.configure(text=txt, font=f)
            color = C["muted"]
            if on.get(name):
                color = {"rec": C["err"], "pause": C["warn"], "mic": C["me"]}.get(name, C["th"])
            if name == "rec" and not self.rec.on and self._armed.get("rec", 0) > time.time():
                color = C["err"]
            b.configure(fg=color)

    def _build_help(self):
        p = self.help = tk.Frame(self.body, bg=C["bg"])
        tk.Label(p, text="Keys and controls", fg=C["th"], bg=C["bg"], font=(self.latin, 12, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(self.px(4), self.px(6)))
        half = (len(HELP) + 1) // 2  # two columns, so it fits a short window
        for i, (k, d) in enumerate(HELP):
            row, col = 1 + i % half, (i // half) * 2
            tk.Label(p, text=k, fg=C["partial"], bg=C["bg"], font=(self.latin, 10, "bold"), anchor="w").grid(
                row=row, column=col, sticky="w", padx=(self.px(36) if col else 0, self.px(14)), pady=1)
            tk.Label(p, text=d, fg=C["th_old"], bg=C["bg"], font=(self.latin, 10), anchor="w").grid(
                row=row, column=col + 1, sticky="w", pady=1)
        tk.Label(p, text="Click anywhere or press any key to close", fg=C["muted"], bg=C["bg"], font=(self.latin, 9)).grid(
            row=half + 1, column=0, columnspan=4, sticky="w", pady=(self.px(8), 0))
        for w in [p] + p.winfo_children():
            w.bind("<Button-1>", lambda e: self.toggle_help())

    def _build_grips(self):
        def grip(edge, cursor, **place):
            g = tk.Frame(self.root, bg=C["bg"], cursor=cursor)
            g.place(**place)
            g.bind("<Button-1>", self._grab)
            g.bind("<B1-Motion>", lambda e: self._resize(e, edge))
            return g
        grip("e", "sb_h_double_arrow", relx=1.0, rely=0, relheight=1.0, x=-1, y=self.px(40), height=-self.px(60), width=self.px(6), anchor="ne")
        grip("s", "sb_v_double_arrow", relx=0, rely=1.0, relwidth=1.0, y=-1, width=-self.px(24), height=self.px(6), anchor="sw")
        n = self.px(16)
        c = tk.Canvas(self.root, width=n, height=n, bg=C["bg"], highlightthickness=0, cursor="size_nw_se")
        for i, j in [(3, 1), (2, 2), (1, 3), (3, 2), (2, 3), (3, 3)]:
            if i + j >= 4:
                x, y = int(n * i / 4.2), int(n * j / 4.2)
                c.create_oval(x - 1, y - 1, x + 1, y + 1, fill=C["faint"], outline="")
        c.place(relx=1.0, rely=1.0, x=-self.px(3), y=-self.px(3), anchor="se")
        c.bind("<Button-1>", self._grab)
        c.bind("<B1-Motion>", lambda e: self._resize(e, "se"))

    def _bind_keys(self):
        r = self.root
        keys = {"r": self.toggle_rec, "m": self.toggle_mic, "t": self.toggle_en, "plus": lambda: self.font(2),
                "equal": lambda: self.font(2), "minus": lambda: self.font(-2), "space": self.toggle_pause,
                "c": self.toggle_compact, "Escape": self.escape, "End": self.to_end, "F1": self.toggle_help,
                "question": self.toggle_help, "KP_Add": lambda: self.font(2), "KP_Subtract": lambda: self.font(-2)}
        for k, f in keys.items():
            for w in (r, self.text):
                w.bind(f"<{k}>" if len(k) > 1 else k, lambda e, f=f: self._key(f))
                if len(k) == 1:
                    w.bind(k.upper(), lambda e, f=f: self._key(f))
        self.text.bind("<Key>", self._readonly)  # text can be selected and copied (Ctrl+C), not typed into
        r.bind_all("<MouseWheel>", lambda e: self.text.yview_scroll(int(-e.delta / 40), "units"))

    def _build_menu(self):
        m = self.menu = tk.Menu(self.root, tearoff=0)
        self.v_en, self.v_mic, self.v_pause = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        self.v_hide, self.v_op = tk.BooleanVar(value=self.hide_capture), tk.IntVar()
        m.add_command(label="Start / stop recording\tR", command=self.toggle_rec)
        m.add_separator()
        m.add_checkbutton(label="Show English\tT", variable=self.v_en, command=self.toggle_en)
        m.add_checkbutton(label="Caption my microphone\tM", variable=self.v_mic, command=self.toggle_mic)
        m.add_checkbutton(label="Pause\tSpace", variable=self.v_pause, command=self.toggle_pause)
        m.add_command(label="Compact / full\tC", command=self.toggle_compact)
        m.add_command(label="Bigger text\t+", command=lambda: self.font(2))
        m.add_command(label="Smaller text\t−", command=lambda: self.font(-2))
        op = tk.Menu(m, tearoff=0)
        for pct in (100, 95, 90, 80, 70):
            op.add_radiobutton(label=f"{pct}%", value=pct, variable=self.v_op, command=lambda p=pct: self.set_opacity(p / 100))
        m.add_cascade(label="Opacity", menu=op)
        m.add_separator()
        m.add_checkbutton(label="Hide from screen sharing", variable=self.v_hide,
                          command=lambda: self.set_capture_hidden(self.v_hide.get()))
        m.add_command(label="Reset size and position", command=self.reset_geometry)
        m.add_command(label="Keys and controls\tF1", command=self.toggle_help)
        m.add_separator()
        m.add_command(label="Quit\tEsc Esc", command=self.quit)

        def popup(e):
            self.v_en.set(self.show_en)
            self.v_mic.set(self.cap.mic_captions)
            self.v_pause.set(self.cap.paused)
            self.v_op.set(int(round(self.opacity * 100)))
            m.tk_popup(e.x_root, e.y_root)
        self.root.bind_all("<Button-3>", popup)

    def _tooltip(self, w, tip):
        w.bind("<Enter>", lambda e: self._set_tip(tip), add="+")
        w.bind("<Leave>", lambda e: self._set_tip(None), add="+")

    # ------------------------------------------------------------------ Windows extras
    def _hwnd(self):
        return ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)  # GA_ROOT

    def _native(self):
        if sys.platform != "win32":
            return
        self.root.update_idletasks()
        try:  # Windows 11: rounded corners
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self._hwnd(), 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        self.set_capture_hidden(self.hide_capture, quiet=True)

    def set_capture_hidden(self, hide, quiet=False):
        """Keep the window out of screen sharing and screenshots (WDA_EXCLUDEFROMCAPTURE, Windows 10 2004+)."""
        ok = False
        if sys.platform == "win32":
            try:
                ok = bool(ctypes.windll.user32.SetWindowDisplayAffinity(self._hwnd(), 0x11 if hide else 0))
            except Exception:
                ok = False
        self.hide_capture = hide and ok
        self.v_hide.set(self.hide_capture)
        if hide and not ok:
            self.toast("Could not hide this window from screen sharing on this Windows version", C["warn"], 6)
        elif not quiet:
            self.toast("Hidden from screen sharing" if hide else "Visible in screen sharing", C["ok"] if hide else C["warn"])
        self._render_placeholder()

    # ------------------------------------------------------------------ moving, resizing, remembering
    def _drag(self, w):
        def press(e):
            self.dx, self.dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()
            self.root.focus_force()
        w.bind("<Button-1>", press, add="+")
        w.bind("<B1-Motion>", lambda e: self.root.geometry(f"+{e.x_root - self.dx}+{e.y_root - self.dy}"), add="+")

    def _grab(self, e):
        self.g0 = (e.x_root, e.y_root, self.root.winfo_width(), self.root.winfo_height())

    def _resize(self, e, edge):
        x0, y0, w0, h0 = self.g0
        if "e" in edge:
            self.w = max(self.px(420), w0 + e.x_root - x0)
        if "s" in edge:
            self.h = max(self.px(120), h0 + e.y_root - y0)
        self.root.geometry(f"{self.w}x{self.h}")
        self.fonts()

    def _on_screen(self, x, y):
        """Keep a remembered position on a screen that still exists (screens may have been unplugged)."""
        try:
            m = ctypes.windll.user32.GetSystemMetrics
            vx, vy, vw, vh = m(76), m(77), m(78), m(79)
        except Exception:
            vx, vy, vw, vh = 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(max(x, vx), vx + vw - self.px(200))
        y = min(max(y, vy), vy + vh - self.px(80))
        return x, y

    def reset_geometry(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.compact = False
        self.w, self.h = int(min(sw * 0.62, self.px(1500))), int(sh * 0.24)
        self.root.geometry(f"{self.w}x{self.h}+{(sw - self.w) // 2}+{int(sh * 0.70)}")
        self.fonts()

    def _load_state(self):
        try:
            with open(self.state_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        h = self._saved[0] if self.compact else self.h
        show_en = self._saved[1] if self.compact else self.show_en
        st = dict(x=self.root.winfo_x(), y=self.root.winfo_y(), w=self.w, h=h, size=self.size, show_en=show_en,
                  opacity=self.opacity)
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(st, f)
        except Exception as e:
            print("[window] could not save the window state:", e, flush=True)

    # ------------------------------------------------------------------ captions
    def fonts(self):
        t = self.text
        t.tag_configure("th", font=(self.thai, self.size), foreground=C["th"], spacing1=self.px(10))
        t.tag_configure("en", font=(self.latin, max(10, self.size - 8)), foreground=C["en"], spacing1=self.px(2),
                        elide=not self.show_en)
        t.tag_configure("me", foreground=C["me"])
        t.tag_configure("th_old", foreground=C["th_old"])
        t.tag_configure("en_old", foreground=C["en_old"])
        t.tag_raise("me")
        t.tag_raise("th_old")
        t.tag_raise("en_old")
        wrap = max(100, self.w - self.px(40))
        self.partial.configure(font=(self.latin, max(10, self.size - 6), "italic"), wraplength=wrap)
        self.placeholder.configure(font=(self.latin, max(10, min(14, self.size - 8))), wraplength=wrap)
        self.status.configure(font=(self.latin, 10))
        self.rec_pill.configure(font=(self.latin, 9, "bold"))
        self.latest.configure(font=(self.latin, 9, "bold"))
        self._paint_buttons()

    def at_end(self):
        return self.text.yview()[1] >= 0.999

    def add_line(self, who, en, th):
        follow = self.at_end()
        t = self.text
        for tag, old in (("th", "th_old"), ("en", "en_old")):
            rng = t.tag_ranges(tag)
            if rng:
                t.tag_add(old, *rng)
        extra = ("me",) if who == "me" else ()
        who_txt = "You · " if who == "me" else ""
        if self.lines:  # the line break after the previous English belongs to it, so hiding the English hides it too
            t.insert("end", "\n", ("en",))
        t.insert("end", who_txt + th + "\n", ("th",) + extra)
        t.insert("end", who_txt + en, ("en",) + extra)
        self.lines.append((who, en, th))
        self._render_placeholder()
        if follow:
            t.see("end")

    def to_end(self):
        self.text.see("end")

    def _render_placeholder(self):
        if not hasattr(self, "placeholder"):
            return
        if self.lines or self.help_on:
            self.placeholder.place_forget()
            return
        if self.state == "error":
            txt, fg = f"Something went wrong\n{self.error}\n\nThe console window has the details.", C["err"]
        elif self.state == "loading":
            txt, fg = f"{self.state_msg}\nLoading the speech and translation models takes about 20 seconds.", C["muted"]
        else:
            src = self.audio.names.get("them")
            share = ("This window is hidden from screen sharing." if self.hide_capture
                     else "This window shows if you share your whole screen: share a single window instead.")
            txt = (f"Listening to {src}\n" if src else "Listening\n") + \
                "Captions appear here when someone speaks.\n\n" + share + "\nPress F1 for keys and controls."
            fg = C["muted"]
            if self.audio.errors and not self.audio.names.get("them"):
                txt, fg = ("Could not open the speaker output\n" + self.audio.errors[0] +
                           "\n\nCheck the Windows default output device, then restart."), C["warn"]
        self.placeholder.configure(text=txt, fg=fg)
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    # ------------------------------------------------------------------ status
    def toast(self, msg, color=None, secs=3.0):
        self._toast = (msg, color or C["th"], time.time() + secs)
        self._render_status()

    def _set_tip(self, tip):
        self._tip = tip
        self._render_status()

    def _render_status(self):
        now = time.time()
        if self._tip:
            txt, fg = self._tip, C["th"]
        elif self._toast and self._toast[2] > now:
            txt, fg = self._toast[0], self._toast[1]
        else:
            self._toast = None
            if self.state == "error":
                txt, fg = "Error: see the caption area", C["err"]
            elif self.state == "loading":
                txt, fg = self.state_msg, C["muted"]
            elif self.cap.paused:
                txt, fg = "Paused. Press Space to go on", C["warn"]
            else:
                src = self.audio.names.get("them")
                bits = ["Live"] + ([src] if src else [])
                if self.cap.mic_captions:
                    bits.append("+ your mic")
                if self.lines and not self.at_end():
                    bits.append("scrolled back, End for the latest")
                txt, fg = "  ·  ".join(bits), C["muted"]
        self.status.configure(text=txt, fg=fg)
        dot = {"loading": C["warn"], "error": C["err"]}.get(self.state, C["faint"] if self.cap.paused else C["ok"])
        if self.state == "loading" and int(now * 2) % 2:
            dot = C["faint"]
        self.dot.itemconfigure(self.dot_id, fill=dot)

    def poll(self):
        while not self.ui_q.empty():
            m = self.ui_q.get()
            if m[0] == "status":
                if m[1].startswith("error"):
                    self.state, self.error = "error", m[1].split(":", 1)[-1].strip()
                elif m[1] == "ready":
                    self.state = "ready"
                else:
                    self.state, self.state_msg = "loading", m[1][:1].upper() + m[1][1:]
                self._render_placeholder()
            elif m[0] == "final":
                self.add_line(*m[1:4])
            elif m[0] == "partial" and (m[1] == "them" or self.cap.mic_captions):
                self.partial.configure(text=m[2])
        self.root.after(100, self.poll)

    def fast_tick(self):
        """Every 0.12 s: hover buttons, level meter, 'latest' pill, status."""
        r = self.root
        try:
            px, py = r.winfo_pointerxy()
            inside = r.winfo_rootx() <= px < r.winfo_rootx() + r.winfo_width() and \
                r.winfo_rooty() <= py < r.winfo_rooty() + r.winfo_height()
        except Exception:
            inside = False
        if inside != self._hover:
            self._hover = inside
            if inside:
                self.btns.grid(row=0, column=4, padx=(self.px(4), 0))
            else:
                self.btns.grid_remove()
                self._tip = None
        lvl = self.audio.level.get("them", 0.0)
        db = 20 * math.log10(lvl + 1e-9)
        target = min(1.0, max(0.0, (db + 60) / 50))
        self._level = max(target, self._level * 0.75)
        self._draw_meter()
        if self.lines and not self.at_end() and not self.help_on:
            self.latest.place(relx=1.0, rely=1.0, x=-self.px(22), y=-self.px(8), anchor="se")
        else:
            self.latest.place_forget()
        self._render_status()
        r.after(120, self.fast_tick)

    def _draw_meter(self):
        c = self.meter
        c.delete("all")
        n, w, h = 7, int(c["width"]), int(c["height"])
        gap = self.px(2)
        bw = (w - gap * (n - 1)) / n
        lit = round(self._level * n)
        for i in range(n):
            bh = h * (0.35 + 0.65 * (i + 1) / n)
            x0 = i * (bw + gap)
            color = (C["ok"] if i < n - 2 else C["warn"]) if i < lit else C["faint"]
            c.create_rectangle(x0, h - bh, x0 + bw, h, fill=color, outline="")

    def tick(self):
        self._paint_rec()
        self.root.after(1000, self.tick)

    # ------------------------------------------------------------------ actions
    def _key(self, f):
        if self.help_on and f not in (self.toggle_help,):
            self.toggle_help()
            return "break"
        f()
        return "break"

    @staticmethod
    def _readonly(e):
        if (e.state & 0x4) and e.keysym.lower() in ("c", "a"):  # Ctrl+C, Ctrl+A
            return None
        if e.keysym in ("Prior", "Next", "Up", "Down", "Home"):
            return None
        return "break"

    def _confirm(self, what, msg, color, secs):
        """True on the second press within `secs`; on the first press show `msg` and wait."""
        if self._armed.get(what, 0) > time.time():
            self._armed.pop(what)
            return True
        self._armed[what] = time.time() + secs
        self.toast(msg, color, secs)
        self._paint_buttons()
        return False

    def toggle_rec(self):
        if self.rec.on:
            where = self.rec.toggle().split("saved: ", 1)[-1]
            try:
                where = os.path.relpath(where)
            except ValueError:
                pass
            self.toast(f"Recording saved to {where}", C["ok"], 8)
        elif self._confirm("rec", "Press R again to start recording. Make sure everyone has agreed.", C["warn"], 5):
            self.rec.toggle()
            self.toast("Recording started", C["err"], 3)
        self._paint_rec()

    def _paint_rec(self):
        if self.rec.on:
            s = self.rec.elapsed()
            self.rec_pill.configure(text=f"● REC  {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}")
            self.rec_pill.grid(row=0, column=3, padx=(self.px(4), self.px(2)))
        else:
            self.rec_pill.grid_remove()
        self._paint_buttons()

    def toggle_mic(self):
        self.cap.mic_captions = not self.cap.mic_captions
        if not self.audio.mic_ok and self.cap.mic_captions:
            self.toast("No microphone was opened, so there is nothing to caption", C["warn"], 5)
        else:
            self.toast("Captioning your microphone too" if self.cap.mic_captions else "Captioning the call only")
        self._paint_buttons()

    def toggle_en(self):
        self.show_en = not self.show_en
        self.fonts()
        self.toast("English shown" if self.show_en else "English hidden")

    def toggle_pause(self):
        self.cap.paused = not self.cap.paused
        if self.cap.paused:
            self.partial.configure(text="")
        self._paint_buttons()

    def toggle_compact(self):
        """Compact: Thai only, window just tall enough for about two lines; press again to go back."""
        self.compact = not self.compact
        if self.compact:
            self._saved = (self.h, self.show_en)
            self.show_en = False
            self.partial.pack_forget()
            ls = tkfont.Font(family=self.thai, size=self.size).metrics("linespace")
            self.h = int(self.head.winfo_height() + 2 * (ls + self.px(10)) + self.px(26))
        else:
            self.h, self.show_en = self._saved
            self.partial.pack(side="bottom", fill="x", padx=self.px(16), pady=(0, self.px(10)), before=self.body)
        self.fonts()
        self.root.geometry(f"{self.w}x{self.h}")
        self.root.update_idletasks()
        self.root.after(30, self.to_end)  # after the new size is laid out, or the view stays where it was

    def toggle_help(self):
        self.help_on = not self.help_on
        if self.help_on:
            self.help.place(relx=0, rely=0, relwidth=1, relheight=1, x=self.px(16))
            self.help.lift()
        else:
            self.help.place_forget()
        self._render_placeholder()

    def font(self, d):
        self.size = min(44, max(12, self.size + d))
        self.fonts()
        self.toast(f"Text size {self.size}")

    def set_opacity(self, v):
        self.opacity = v
        self.root.attributes("-alpha", v)

    def escape(self):
        if self._confirm("quit", "Press Esc again to quit", C["warn"], 2.5):
            self.quit()

    def quit(self):
        if self.rec.on:
            print("[rec]", self.rec.toggle(), flush=True)
        self._save_state()
        self.audio.stop.set()
        self.root.destroy()
