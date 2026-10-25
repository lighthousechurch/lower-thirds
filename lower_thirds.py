#!/usr/bin/env python3
"""Convert sermon slide JPGs into 1920x1080 transparent lower-third PNGs.

Usage:
  lower_thirds.py ocr SLIDE... > texts.json          # read text from slides 2..N
  lower_thirds.py render texts.json OUT_DIR [--zip NAME]

texts.json is the JSON list written by `ocr` ({"file", "text"} per slide, in
order). Fill in slide 1's text with the sermon title and fix any misreads
before rendering. A plain list of strings also works.
"""
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = HERE / "fonts" / "SourceSerif4-Bold.ttf"
BAND = HERE / "design_handoff_lower_thirds" / "band.png"

W, H = 1920, 1080
BAND_Y = 880
CENTER_Y = 980
LEFT = 88
MAX_W = W - 2 * LEFT
SIZE = 58
MAX_LINES = 2
COLOR = (0x1B, 0x2A, 0x33, 255)
# Slide 1 (sermon title) matches the larger single-line title in reference/01.png.
TITLE_SIZE = 79
TITLE_BASELINE = 998


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(p).name)]


# --- OCR --------------------------------------------------------------------

def _tesseract(im):
    out = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng"],
                         input=_png_bytes(im), capture_output=True, check=True).stdout.decode("utf-8")
    text = re.sub(r"\s*\n\s*", " ", out).replace("|", "I")
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"[^\x20-\x7E‘-”—…]", "", text)
    return text.strip()


def _otsu(gray):
    hist = np.bincount(gray.ravel(), minlength=256).astype(float)
    total, sum_all = gray.size, np.dot(np.arange(256), hist)
    best, thresh, w_b, sum_b = -1.0, 128, 0.0, 0.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0 or w_b == total:
            continue
        sum_b += t * hist[t]
        m_b, m_f = sum_b / w_b, (sum_all - sum_b) / (total - w_b)
        between = w_b * (total - w_b) * (m_b - m_f) ** 2
        if between > best:
            best, thresh = between, t
    return thresh


def _words(text):
    return sum(len(w) > 1 and w.isalpha() for w in re.findall(r"[A-Za-z']+", text))


def ocr(path):
    """Read a slide's text. Tries several clean-ups and keeps the one with the most real words."""
    rgb = np.asarray(Image.open(path).convert("RGB"))
    gray = np.asarray(Image.open(path).convert("L"))
    t = _otsu(gray)
    candidates = [
        np.where(rgb.min(axis=2) > 232, 0, 255),  # white text on the blue texture
        np.where(gray > t, 0, 255),               # light text, any background
        np.where(gray > t, 255, 0),               # dark text, any background
    ]
    texts = [_tesseract(Image.fromarray(c.astype(np.uint8))) for c in candidates]
    return max(texts, key=_words)


def _png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# --- Layout & render ----------------------------------------------------------

def wrap(font, text):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}" if cur else w
        if font.getlength(t) > MAX_W and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def truncate(font, text, max_lines):
    lines = wrap(font, text)
    if len(lines) <= max_lines:
        return lines
    last = ""
    for w in " ".join(lines[max_lines - 1:]).split(" "):
        t = f"{last} {w}" if last else w
        if font.getlength(t + "...") > MAX_W:
            break
        last = t
    return lines[:max_lines - 1] + [re.sub(r"[,;:.\s]+$", "", last) + "..."]


def render(text, band, title=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste(band, (0, BAND_Y))
    d = ImageDraw.Draw(img)
    if title:
        size = TITLE_SIZE
        font = ImageFont.truetype(str(FONT), size)
        while font.getlength(text) > MAX_W and size > SIZE:
            size -= 2
            font = ImageFont.truetype(str(FONT), size)
        line = truncate(font, text.strip(), 1)[0]
        d.text((LEFT, TITLE_BASELINE), line, font=font, fill=COLOR, anchor="ls")
        return img, [line]
    font = ImageFont.truetype(str(FONT), SIZE)
    lines = truncate(font, (text or "").strip(), MAX_LINES)
    lh = round(SIZE * 1.04)
    n = len(lines)
    for i, line in enumerate(lines):
        y = CENTER_Y - (n - 1) * lh / 2 + i * lh + SIZE * 0.33
        d.text((LEFT, y), line, font=font, fill=COLOR, anchor="ls")
    return img, lines


def build(texts, out, zip_name=None):
    """Render texts (slide 1 = title) to out/01.png ... and optionally zip them."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    band = Image.open(BAND).convert("RGBA").resize((W, H - BAND_Y))
    pad = max(2, len(str(len(texts))))
    names = []
    for i, t in enumerate(texts, 1):
        img, lines = render(t, band, title=(i == 1))
        name = f"{i:0{pad}d}.png"
        # Reduce to 256 colours (looks identical) but save as a normal RGBA PNG:
        # ~230 KB instead of ~560 KB, so long sermons fit under Gmail's 25 MB limit.
        # Palette PNGs came through blank on the stream team's iPhone (Oct 24).
        img = img.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).convert("RGBA")
        img.save(out / name, optimize=True)
        names.append(name)
        print(name, "|", " / ".join(lines))
    if not zip_name:
        return None
    zpath = out / zip_name
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(out / name, name)
    print("zip:", zpath)
    return zpath


def main():
    cmd = sys.argv[1]
    if cmd == "ocr":
        slides = sorted(sys.argv[2:], key=natural_key)
        texts = [""] + [ocr(p) for p in slides[1:]]
        json.dump([{"file": Path(p).name, "text": t} for p, t in zip(slides, texts)],
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif cmd == "render":
        texts = [e["text"] if isinstance(e, dict) else e for e in json.load(open(sys.argv[2]))]
        zip_name = sys.argv[sys.argv.index("--zip") + 1] if "--zip" in sys.argv else None
        build(texts, Path(sys.argv[3]), zip_name)

if __name__ == "__main__":
    main()
