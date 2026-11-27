"""Draws the app icon (live_captions/assets/app.ico): a dark rounded square with a blue caption bubble holding a white
line and a yellow line, like the caption window. Run: python tools/make_icon.py"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_captions", "assets", "app.ico")
S = 1024  # draw large, then scale down


def draw():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((32, 32, S - 32, S - 32), radius=220, fill="#141A22", outline="#2A3340", width=16)
    # caption bubble with a tail at the bottom left
    d.rounded_rectangle((150, 230, S - 150, 700), radius=120, fill="#3D8BFD")
    d.polygon([(270, 660), (430, 660), (250, 850)], fill="#3D8BFD")
    # a long white line (the Thai) and a shorter yellow line (the English being spoken)
    d.rounded_rectangle((250, 360, S - 250, 440), radius=40, fill="#FFFFFF")
    d.rounded_rectangle((250, 500, 600, 580), radius=40, fill="#F2CE5C")
    return im


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im = draw()
    im.save(OUT, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    im.resize((256, 256), Image.LANCZOS).save(OUT.replace(".ico", ".png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
