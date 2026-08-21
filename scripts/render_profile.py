#!/usr/bin/env python3
"""Render Thomas Fairhurst's Neofetch-style GitHub profile card.

The curated transparent PNG is the canonical portrait artwork. This script
builds the deterministic SVG card and its aligned 39 x 25 text layer.
"""

from __future__ import annotations

import argparse
import base64
import html
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class Palette:
    background: str
    text: str
    connector: str
    key: str
    value: str


PALETTE = Palette(
    background="#161b22",
    text="#c9d1d9",
    connector="#616e7f",
    key="#ffa657",
    value="#a5d6ff",
)

RIGHT_ROWS: tuple[tuple[str, str, str], ...] = (
    ("header", "thomas@luzivog", ""),
    ("meta", "Name", "Thomas Fairhurst"),
    ("meta", "Role", "Co-founder & CTO at Leadlord"),
    ("meta", "Building", "Compliant campaigns, fast & affordable"),
    ("meta", "Education", "McGill CS → Imperial Advanced Computing"),
    ("blank", "", ""),
    ("meta", "Previously", "PhoneHost — AI call handling for restaurants"),
    ("meta", "Open Source", "toks, agentdictate"),
    ("meta", "Following.Runtime", "Bun"),
    ("meta", "Following.Desktop", "GPUI"),
    ("meta", "Following.Database", "SpacetimeDB"),
    ("meta", "Principle", "Keep it simple, stupid."),
    ("blank", "", ""),
    ("section", "Contact", ""),
    ("meta", "GitHub", "github.com/Luzivog"),
    ("meta", "Website", "thomas-fairhurst.com"),
    ("meta", "LinkedIn", "linkedin.com/in/thomas-fht"),
    ("blank", "", ""),
    ("section", "Projects", ""),
    ("meta", "Leadlord", "Compliant marketing campaigns"),
    ("meta", "PhoneHost", "AI call handling for restaurants"),
    ("meta", "toks", "Local AI coding usage tracker"),
    ("meta", "agentdictate", "Native Linux voice dictation"),
    ("blank", "", ""),
    ("meta", "Visibility", "Most of my work is private"),
)

ROW_COUNT = 25
ROW_START = 30
ROW_HEIGHT = 20
RIGHT_X = 390
RIGHT_WIDTH = 62
PORTRAIT_COLUMNS = 39
ASCII_BUCKETS = (
    ".,",
    ".,:;",
    ":;ir",
    "irsX",
    "sXA2",
    "A253",
    "3hMH",
    "HGS#",
    "S#9B",
    "9B&@",
)


def separator_tail(label: str) -> str:
    return " -" + "—" * max(1, RIGHT_WIDTH - len(label) - 2)


def metadata_svg() -> str:
    rendered: list[str] = []
    for index, (kind, label, value) in enumerate(RIGHT_ROWS):
        y = ROW_START + index * ROW_HEIGHT
        if kind == "header":
            rendered.append(
                f'<tspan x="{RIGHT_X}" y="{y}">{html.escape(label)}</tspan>'
                f"{separator_tail(label)}"
            )
        elif kind == "section":
            heading = f"- {label}"
            rendered.append(
                f'<tspan x="{RIGHT_X}" y="{y}">{html.escape(heading)}</tspan>'
                f"{separator_tail(heading)}"
            )
        elif kind == "blank":
            rendered.append(f'<tspan x="{RIGHT_X}" y="{y}" class="cc">. </tspan>')
        else:
            fixed_length = len(". ") + len(label) + len(":") + len(value) + 2
            dots = "." * max(1, RIGHT_WIDTH - fixed_length)
            rendered.append(
                f'<tspan x="{RIGHT_X}" y="{y}" class="cc">. </tspan>'
                f'<tspan class="key">{html.escape(label)}</tspan>:'
                f'<tspan class="cc"> {dots} </tspan>'
                f'<tspan class="value">{html.escape(value)}</tspan>'
            )
    return "\n".join(rendered)


def load_portrait(path: Path) -> tuple[bytes, Image.Image]:
    encoded = path.read_bytes()
    with Image.open(path) as source:
        source.load()
        if source.format != "PNG":
            raise ValueError(f"{path} must be a PNG image")
        portrait = source.convert("RGBA")
    return encoded, portrait


def visible_color(red: int, green: int, blue: int) -> str:
    if max(red, green, blue) < 120:
        red = round(red * 0.72 + 255 * 0.28)
        green = round(green * 0.72 + 255 * 0.28)
        blue = round(blue * 0.72 + 255 * 0.28)
    return f"#{red:02x}{green:02x}{blue:02x}"


def portrait_ascii_svg(portrait: Image.Image) -> str:
    colors = portrait.resize((PORTRAIT_COLUMNS, ROW_COUNT), Image.Resampling.BOX)
    alpha = colors.getchannel("A")

    rows: list[str] = []
    for row in range(ROW_COUNT):
        cells: list[str] = []
        for column in range(PORTRAIT_COLUMNS):
            opacity = alpha.getpixel((column, row))
            if opacity < 24:
                cells.append(" ")
                continue

            bucket = ASCII_BUCKETS[
                round((opacity / 255) * (len(ASCII_BUCKETS) - 1))
            ]
            seed = ((column + 1) * 73856093) ^ ((row + 1) * 19349663)
            seed = (seed ^ (seed >> 13)) * 1274126177
            character = bucket[seed % len(bucket)]
            red, green, blue, _ = colors.getpixel((column, row))
            cells.append(
                f'<tspan fill="{visible_color(red, green, blue)}" '
                f'fill-opacity="{(opacity / 255) * 0.36:.2f}">{html.escape(character)}</tspan>'
            )
        rows.append(
            f'<tspan x="5" y="{ROW_START + row * ROW_HEIGHT}">{"".join(cells)}</tspan>'
        )
    return "\n".join(rows)


def profile_svg(portrait_path: Path) -> str:
    if len(RIGHT_ROWS) != ROW_COUNT:
        raise ValueError("Metadata must occupy exactly 25 terminal rows")

    portrait_bytes, portrait_image = load_portrait(portrait_path)
    portrait = base64.b64encode(portrait_bytes).decode("ascii")
    ascii_portrait = portrait_ascii_svg(portrait_image)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py. -->
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,'DejaVu Sans Mono',monospace" width="990px" height="530px" font-size="16px" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate. Following Bun, GPUI, and SpacetimeDB. Keep it simple, stupid.</desc>
  <style>
    @font-face {{
      src: local('Consolas'), local('Consolas Bold');
      font-family: 'ConsolasFallback';
      font-display: swap;
      -webkit-size-adjust: 109%;
      size-adjust: 109%;
    }}
    .key {{ fill: {PALETTE.key}; font-weight: 600; }}
    .value {{ fill: {PALETTE.value}; }}
    .cc {{ fill: {PALETTE.connector}; }}
    text, tspan {{ white-space: pre; }}
  </style>
  <rect width="990px" height="530px" fill="{PALETTE.background}" rx="15"/>
  <image x="5" y="10" width="380" height="510" opacity="0.90" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{portrait}"/>
  <text>
  {ascii_portrait}
  </text>
  <text x="{RIGHT_X}" y="{ROW_START}" fill="{PALETTE.text}">
  {metadata_svg()}
  </text>
</svg>
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portrait", default=Path("assets/portrait-ascii.png"), type=Path)
    parser.add_argument("--output", default=Path("assets/profile.svg"), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(profile_svg(args.portrait), encoding="utf-8")


if __name__ == "__main__":
    main()
