#!/usr/bin/env python3
"""Render a Fastfetch profile card from Thomas's GitHub avatar.

The portrait is rendered as a crisp truecolor terminal pixel mosaic (chafa-style
half-block aesthetic) from assets/avatar.png, the GitHub profile photo from
https://avatars.githubusercontent.com/u/57810766?v=4 (2026-09-05).

Run from the repository root with Python 3 and Pillow:
    python3 scripts/render_profile.py
"""

from __future__ import annotations

import argparse
import base64
from collections import deque
import html
import io
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


BACKGROUND = "#161b22"
BG_RGB = (22, 27, 34)
TEXT = "#c9d1d9"
MUTED = "#697787"
KEY = "#ffa657"
VALUE = "#a5d6ff"

RIGHT_ROWS: tuple[tuple[str, str, str], ...] = (
    ("section", "Who am I?", ""),
    ("meta", "Name", "Thomas Fairhurst"),
    ("meta", "Role", "Co-founder & CTO at Leadlord"),
    ("meta", "Building", "Compliant marketing, fast & affordable"),
    ("meta", "Education", "Imperial MSc student · McGill CS grad"),
    ("blank", "", ""),
    ("meta", "Previously", "PhoneHost — AI Host for Restaurants"),
    ("meta", "Open Source", "toks, agentdictate"),
    ("meta", "Following", "Bun · GPUI · SpacetimeDB · Omarchy"),
    ("meta", "Principle", "Keep it simple, stupid."),
    ("meta", "Offline", "Poker · Gym"),
    ("blank", "", ""),
    ("section", "Contact", ""),
    ("meta", "GitHub", "github.com/Luzivog"),
    ("meta", "Website", "thomasfairhurst.com"),
    ("meta", "LinkedIn", "linkedin.com/in/thomas-fht"),
    ("meta", "X", "x.com/luzivog"),
    ("blank", "", ""),
    ("section", "Projects", ""),
    ("meta", "Leadlord", "Compliant marketing campaigns"),
    ("meta", "PhoneHost", "AI Host for Restaurants"),
    ("meta", "toks", "Local AI coding usage tracker"),
    ("meta", "agentdictate", "Native Linux voice dictation"),
    ("meta", "Planner", "Imperial module planner"),
)


FONT_SIZE = 16
CELL_WIDTH = 9.64
ROW_HEIGHT = 20
ROW_START = 60
RIGHT_X = 456
VALUE_X = RIGHT_X + 14 * CELL_WIDTH
WIDTH = 1006
HEIGHT = ROW_START + (len(RIGHT_ROWS) - 1) * ROW_HEIGHT + 30

# Portrait geometry aligned to the prompt column (x=24), "Who am I?" cap top
# (y=48), and the "Planner:" row (y=524), leaving a ~42px gutter before RIGHT_X.
PORTRAIT_X = 22
PORTRAIT_Y = 48
PORTRAIT_WIDTH = 392
PORTRAIT_HEIGHT = 476
GRID_COLS = 100
GRID_ROWS = 122
BLOCK_SCALE = 4


def smoothstep(value: float) -> float:
    clamped = max(0.0, min(1.0, value))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def text(x: float, y: float, content: str, color: str, extra: str = "") -> str:
    return (f'<text x="{x:g}" y="{y:g}" fill="{color}"{extra}>'
            f'{html.escape(content)}</text>')


def metadata_svg() -> str:
    """Give every label and value an explicit, stable starting column."""
    rendered: list[str] = []
    for index, (kind, label, value) in enumerate(RIGHT_ROWS):
        y = ROW_START + index * ROW_HEIGHT
        if kind == "section":
            rendered.append(text(RIGHT_X, y, label, TEXT))
        elif kind == "meta":
            rendered.append(text(RIGHT_X, y, label + ":", KEY,
                                 ' font-weight="bold"'))
            rendered.append(text(VALUE_X, y, value, VALUE))
    return "\n".join(rendered)


def segment_foreground(source: Image.Image) -> Image.Image:
    """Separate the dark backdrop from hair/shirt via border-seeded flood fill."""
    width, height = source.size
    pixels = source.load()

    # Dark neutral pixels reachable from the image borders belong to the night
    # backdrop; warm dark curls inside the silhouette are left untouched.
    bg_candidate = bytearray(width * height)
    bokeh_y = int(height * 380 / 460)
    bokeh_x = int(width * 155 / 460)
    for y in range(height):
        row_offset = y * width
        for x in range(width):
            r, g, b = pixels[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            chroma = max(r, g, b) - min(r, g, b)
            if (lum < 30.0 and chroma < 16.0) or (y >= bokeh_y and x < bokeh_x):
                bg_candidate[row_offset + x] = 1

    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    right_border_limit = int(height * 320 / 460)

    def seed(x: int, y: int) -> None:
        idx = y * width + x
        if bg_candidate[idx] and not background[idx]:
            background[idx] = 1
            queue.append((x, y))

    for x in range(width):
        seed(x, 0)
    for y in range(height):
        seed(0, y)
        if y < right_border_limit:
            seed(width - 1, y)

    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < width and 0 <= ny < height:
                idx = ny * width + nx
                if bg_candidate[idx] and not background[idx]:
                    background[idx] = 1
                    queue.append((nx, ny))

    # Keep the largest connected foreground component (head and torso) so stray
    # background lights never survive as floating speckles.
    visited = bytearray(width * height)
    best_component: list[int] = []
    for y in range(height):
        for x in range(width):
            start = y * width + x
            if background[start] or visited[start]:
                continue
            comp: list[int] = [start]
            visited[start] = 1
            q = deque([(x, y)])
            while q:
                cx, cy = q.popleft()
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        idx = ny * width + nx
                        if not background[idx] and not visited[idx]:
                            visited[idx] = 1
                            comp.append(idx)
                            q.append((nx, ny))
            if len(comp) > len(best_component):
                best_component = comp

    fg_bytes = bytearray(width * height)
    for idx in best_component:
        fg_bytes[idx] = 255

    mask = Image.frombytes("L", (width, height), bytes(fg_bytes))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.4))
    return mask.point(lambda v: max(0, min(255, int((v / 255.0 - 0.14) / 0.80 * 255))))


def balance_flash(source: Image.Image) -> Image.Image:
    """Soften direct-flash speculars while keeping natural skin and dark curls."""
    width, height = source.size
    pixels = source.load()
    balanced = Image.new("RGB", (width, height))
    out = balanced.load()

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            l_in = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            if l_in > 0.62:
                l_out = 0.62 + (l_in - 0.62) * 0.58
            elif l_in < 0.26:
                l_out = l_in * 1.15
            else:
                l_out = l_in
            scale = l_out / l_in if l_in > 1e-4 else 1.0
            out[x, y] = (
                min(255, int(r * scale)),
                min(255, int(g * scale)),
                min(255, int(b * scale)),
            )

    balanced = balanced.filter(ImageFilter.UnsharpMask(radius=14, percent=12, threshold=2))
    balanced = ImageEnhance.Contrast(balanced).enhance(1.06)
    balanced = ImageEnhance.Color(balanced).enhance(0.95)
    return balanced.filter(ImageFilter.UnsharpMask(radius=1.1, percent=50, threshold=2))


def portrait_svg(path: Path) -> str:
    """Render a crisp truecolor terminal-block bust seamlessly blended into #161b22."""
    with Image.open(path) as raw:
        source = ImageOps.exif_transpose(raw).convert("RGB")

    width, height = source.size
    alpha_full = segment_foreground(source)
    graded = balance_flash(source)

    # Align cap top (y=84) flush with "Who am I?" and left brim/curls (x=80..86)
    # with the prompt column, extending the full burgundy bust to "Planner:".
    top = height * 82 / 460
    crop_h = height * 377 / 460
    crop_w = crop_h * PORTRAIT_WIDTH / PORTRAIT_HEIGHT
    left = width * 79 / 460
    box = (left, top, left + crop_w, top + crop_h)

    crop_rgb = graded.crop(box)
    crop_alpha = alpha_full.crop(box)
    cw, ch = crop_rgb.size
    rgb_px = crop_rgb.load()
    a_px = crop_alpha.load()

    # Preserve 100% rich burgundy across the collar and upper chest; fade only
    # the bottom 15% and a sloped outer-right shoulder contour into #161b22 so
    # the head never floats and no shoulder highlight wisp extends past the fade.
    composited = Image.new("RGB", (cw, ch), BG_RGB)
    comp_px = composited.load()
    feathered_alpha = Image.new("L", (cw, ch), 0)
    fa_px = feathered_alpha.load()

    for y in range(ch):
        yy = y / max(1, ch - 1)
        bottom_fade = smoothstep((0.99 - yy) / 0.15)
        shoulder_weight = smoothstep((yy - 0.63) / 0.05)
        # Slope the outer-right shoulder boundary gently outward as yy descends
        # so the upper shoulder fabric highlight is cleanly tucked inside the fade.
        right_limit = 0.90 + 0.08 * smoothstep((yy - 0.66) / 0.22)
        for x in range(cw):
            xx = x / max(1, cw - 1)
            right_edge = smoothstep((right_limit - xx) / 0.13)
            right_fade = 1.0 - shoulder_weight * (1.0 - right_edge)
            a = (a_px[x, y] / 255.0) * bottom_fade * right_fade
            fa_px[x, y] = int(a * 255)
            r, g, b = rgb_px[x, y]
            comp_px[x, y] = (
                int(r * a + BG_RGB[0] * (1.0 - a)),
                int(g * a + BG_RGB[1] * (1.0 - a)),
                int(b * a + BG_RGB[2] * (1.0 - a)),
            )

    small = composited.resize((GRID_COLS, GRID_ROWS), Image.Resampling.LANCZOS)
    small_alpha = feathered_alpha.resize((GRID_COLS, GRID_ROWS), Image.Resampling.LANCZOS)
    s_px = small.load()
    sa_px = small_alpha.load()
    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            if sa_px[x, y] < 10:
                s_px[x, y] = BG_RGB

    # Pre-upscale by an exact integer factor so pixel cells remain razor-sharp
    # even on viewers that ignore image-rendering="pixelated".
    crisp = small.resize(
        (GRID_COLS * BLOCK_SCALE, GRID_ROWS * BLOCK_SCALE),
        Image.Resampling.NEAREST,
    )
    encoded = io.BytesIO()
    crisp.save(encoded, format="PNG", optimize=True)
    b64 = base64.b64encode(encoded.getvalue()).decode("ascii")
    return (
        f'<image x="{PORTRAIT_X}" y="{PORTRAIT_Y}" '
        f'width="{PORTRAIT_WIDTH}" height="{PORTRAIT_HEIGHT}" '
        f'image-rendering="pixelated" aria-hidden="true" '
        f'href="data:image/png;base64,{b64}"/>'
    )


def profile_svg(portrait_path: Path) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py from the GitHub profile avatar. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" font-family="'DejaVu Sans Mono',Consolas,monospace" font-size="{FONT_SIZE}" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">A Fastfetch-style profile with a truecolor terminal pixel portrait made from Thomas's GitHub avatar. Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate.</desc>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="{BACKGROUND}" rx="15"/>
  <text x="24" y="28" fill="{TEXT}"><tspan fill="{VALUE}">~</tspan><tspan fill="{MUTED}"> › </tspan>fastfetch</text>
  {portrait_svg(portrait_path)}
  <g>{metadata_svg()}</g>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portrait", default=Path("assets/avatar.png"), type=Path)
    parser.add_argument("--output", default=Path("assets/profile-portrait.svg"), type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(profile_svg(args.portrait), encoding="utf-8")


if __name__ == "__main__":
    main()
