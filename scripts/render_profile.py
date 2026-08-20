#!/usr/bin/env python3
"""Render Thomas Fairhurst's horizontal GitHub profile card.

The portrait is sampled into thousands of individually colored ASCII glyphs.
The source photograph is supplied at render time and is never copied into the
repository.
"""

from __future__ import annotations

import argparse
import html
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ASCII_RAMP = ".,:;irsXA253hMHGS#9B&@"


@dataclass(frozen=True)
class Palette:
    background: str
    text: str
    connector: str
    key: str
    value: str


PALETTES = {
    "dark": Palette(
        background="#161b22",
        text="#c9d1d9",
        connector="#616e7f",
        key="#ffa657",
        value="#a5d6ff",
    ),
    "light": Palette(
        background="#f6f8fa",
        text="#24292f",
        connector="#c2cfde",
        key="#953800",
        value="#0a3069",
    ),
}


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


def crop_portrait(source: Image.Image) -> Image.Image:
    width, height = source.size
    # Tight enough for facial definition while retaining the cap and shoulders.
    return source.crop(
        (
            round(width * 0.10),
            round(height * 0.17),
            round(width * 0.88),
            round(height * 0.84),
        )
    )


def crop_to_subject(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Remove the dark venue background and retain the connected silhouette."""
    grayscale = ImageOps.grayscale(image)
    mask = grayscale.point(lambda value: 255 if value > 26 else 0)

    # Opening removes isolated venue lights; closing reconnects hair and clothing.
    mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(7))
    mask = mask.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.MinFilter(15))

    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError("Could not isolate a foreground subject from the portrait")

    left, top, right, bottom = bounds
    pad_x = round((right - left) * 0.025)
    pad_y = round((bottom - top) * 0.025)
    subject_bounds = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )
    return image.crop(subject_bounds), mask.crop(subject_bounds)


def fill_mask_holes(mask: Image.Image, *, columns: int, rows: int) -> list[list[bool]]:
    sampled = mask.resize((columns, rows), Image.Resampling.BOX)
    foreground = [
        [sampled.getpixel((column, row)) >= 72 for column in range(columns)]
        for row in range(rows)
    ]

    exterior: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for column in range(columns):
        queue.extend(((column, 0), (column, rows - 1)))
    for row in range(rows):
        queue.extend(((0, row), (columns - 1, row)))

    while queue:
        column, row = queue.popleft()
        if (
            not (0 <= column < columns and 0 <= row < rows)
            or foreground[row][column]
            or (column, row) in exterior
        ):
            continue
        exterior.add((column, row))
        queue.extend(
            (
                (column - 1, row),
                (column + 1, row),
                (column, row - 1),
                (column, row + 1),
            )
        )

    return [
        [foreground[row][column] or (column, row) not in exterior for column in range(columns)]
        for row in range(rows)
    ]


def ascii_portrait(path: Path, *, columns: int, rows: int) -> tuple[str, ...]:
    with Image.open(path) as source:
        cropped = crop_portrait(source.convert("RGB"))
    subject, mask = crop_to_subject(cropped)

    luminance = ImageOps.grayscale(subject)
    luminance = ImageOps.autocontrast(luminance, cutoff=(1, 2), mask=mask)
    luminance = ImageEnhance.Contrast(luminance).enhance(1.18)
    luminance = luminance.filter(
        ImageFilter.UnsharpMask(radius=1.8, percent=180, threshold=3)
    )
    luminance = Image.composite(
        luminance, Image.new("L", luminance.size, 0), mask
    ).resize((columns, rows), Image.Resampling.LANCZOS)
    foreground = fill_mask_holes(mask, columns=columns, rows=rows)

    rendered: list[str] = []
    for row in range(rows):
        characters: list[str] = []
        for column in range(columns):
            if not foreground[row][column]:
                characters.append(" ")
                continue

            normalized = luminance.getpixel((column, row)) / 255
            ramp_index = round((normalized**0.96) * (len(ASCII_RAMP) - 1))
            characters.append(ASCII_RAMP[ramp_index])
        rendered.append("".join(characters).rstrip())

    return tuple(rendered)


def portrait_svg(rows: tuple[str, ...]) -> str:
    return "\n".join(
        f'<tspan x="15" y="{ROW_START + index * ROW_HEIGHT}">'
        f"{html.escape(row)}</tspan>"
        for index, row in enumerate(rows)
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
            rendered.append(
                f'<tspan x="{RIGHT_X}" y="{y}" class="cc">. </tspan>'
            )
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


def svg_style(palette: Palette) -> str:
    return f"""
  <style>
    @font-face {{
      src: local('Consolas'), local('Consolas Bold');
      font-family: 'ConsolasFallback';
      font-display: swap;
      -webkit-size-adjust: 109%;
      size-adjust: 109%;
    }}
    .key {{ fill: {palette.key}; font-weight: 600; }}
    .value {{ fill: {palette.value}; }}
    .cc {{ fill: {palette.connector}; }}
    text, tspan {{ white-space: pre; }}
  </style>"""


def profile_svg(
    portrait: tuple[str, ...], *, palette: Palette
) -> str:
    if len(portrait) != ROW_COUNT or len(RIGHT_ROWS) != ROW_COUNT:
        raise ValueError("The portrait and metadata must both occupy exactly 25 rows")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py. The source portrait is not stored. -->
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="985px" height="530px" font-size="16px" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate. Following Bun, GPUI, and SpacetimeDB. Keep it simple, stupid.</desc>
{svg_style(palette)}
  <rect width="985px" height="530px" fill="{palette.background}" rx="15"/>
  <text x="15" y="30" fill="{palette.text}" class="ascii">
  {portrait_svg(portrait)}
  </text>
  <text x="{RIGHT_X}" y="{ROW_START}" fill="{palette.text}">
  {metadata_svg()}
  </text>
</svg>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portrait", required=True, type=Path)
    parser.add_argument("--output", default=Path("assets"), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    portrait = ascii_portrait(args.portrait, columns=39, rows=ROW_COUNT)

    for theme, palette in PALETTES.items():
        (args.output / f"profile-{theme}.svg").write_text(
            profile_svg(portrait, palette=palette), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
