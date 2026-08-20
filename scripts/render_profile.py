#!/usr/bin/env python3
"""Render Thomas Fairhurst's horizontal GitHub profile card.

The portrait is sampled into thousands of individually colored ASCII glyphs.
The source photograph is supplied at render time and is never copied into the
repository.
"""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


FONT_STACK = (
    "'DejaVu Sans Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, "
    "Consolas, 'Liberation Mono', monospace"
)
ASCII_RAMP = " .`^\",:;Il!i~+_-?][}{1)(|\\/*tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


@dataclass(frozen=True)
class Palette:
    background: str
    border: str
    text: str
    muted: str
    label: str
    value: str


@dataclass(frozen=True)
class AsciiCell:
    character: str
    color: tuple[int, int, int]
    luminance: float


PALETTES = {
    "dark": Palette(
        background="#0d0f12",
        border="#2b3038",
        text="#eee9e2",
        muted="#7f8995",
        label="#b96779",
        value="#a5d6ff",
    ),
    "light": Palette(
        background="#faf8f4",
        border="#d8d1c8",
        text="#2d2927",
        muted="#8d847d",
        label="#833b4d",
        value="#0969da",
    ),
}


PROFILE_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Name", ("Thomas Fairhurst",)),
    ("Role", ("Co-founder & CTO at Leadlord",)),
    ("Building", ("Compliant marketing campaigns,", "fast and affordable")),
    ("Previously", ("PhoneHost — AI call handling", "for restaurants")),
    ("Open source", ("toks · agentdictate",)),
    ("Following", ("Bun · GPUI · SpacetimeDB",)),
    ("Principle", ("Keep it simple, stupid.",)),
    ("Education", ("McGill CS → Imperial MSc", "Advanced Computing")),
)


ANSI_SWATCHES = (
    (
        "#454b58",
        "#a95b6a",
        "#63997b",
        "#b49a62",
        "#678db8",
        "#9574aa",
        "#6f9eaa",
        "#a9adb5",
    ),
    (
        "#697181",
        "#d9788b",
        "#89c7a4",
        "#dec47e",
        "#8ab7e8",
        "#bd94d3",
        "#91c7d3",
        "#eee9e2",
    ),
)


def crop_portrait(source: Image.Image) -> Image.Image:
    width, height = source.size
    # Tight enough for facial definition while retaining the cap and shoulders.
    return source.crop(
        (
            round(width * 0.10),
            round(height * 0.17),
            round(width * 0.88),
            round(height * 0.91),
        )
    )


def ascii_portrait(
    path: Path, *, columns: int, rows: int
) -> tuple[tuple[AsciiCell, ...], ...]:
    with Image.open(path) as source:
        color_image = crop_portrait(source.convert("RGB"))

    sampled_color = color_image.resize((columns, rows), Image.Resampling.LANCZOS)
    sampled_luminance = ImageOps.grayscale(color_image)
    sampled_luminance = ImageOps.autocontrast(sampled_luminance, cutoff=(1, 2))
    sampled_luminance = ImageEnhance.Contrast(sampled_luminance).enhance(1.06)
    sampled_luminance = ImageEnhance.Sharpness(sampled_luminance).enhance(2.4)
    sampled_luminance = sampled_luminance.resize(
        (columns, rows), Image.Resampling.LANCZOS
    )

    rendered: list[tuple[AsciiCell, ...]] = []
    for row in range(rows):
        cells: list[AsciiCell] = []
        for column in range(columns):
            luminance = sampled_luminance.getpixel((column, row))
            if luminance < 9:
                cells.append(AsciiCell(" ", (0, 0, 0), 0.0))
                continue

            normalized = min(1.0, luminance / 255)
            ramp_index = round((normalized**1.08) * (len(ASCII_RAMP) - 1))
            cells.append(
                AsciiCell(
                    ASCII_RAMP[ramp_index],
                    sampled_color.getpixel((column, row)),
                    normalized,
                )
            )
        rendered.append(tuple(cells))

    return tuple(rendered)


def adjusted_color(cell: AsciiCell, theme: str) -> str:
    red, green, blue = cell.color
    if theme == "dark":
        # Lift dark hair and shirt tones without washing out the original color.
        mix = 0.35 + (1.0 - cell.luminance) * 0.10
        red = round(red + (255 - red) * mix)
        green = round(green + (255 - green) * mix)
        blue = round(blue + (255 - blue) * mix)
    else:
        # Darken the photographic palette so the glyphs stay legible on ivory.
        scale = 0.56
        red = round(red * scale)
        green = round(green * scale)
        blue = round(blue * scale)

    # Small quantization keeps the portrait cohesive instead of visually noisy.
    red = min(255, round(red / 6) * 6)
    green = min(255, round(green / 6) * 6)
    blue = min(255, round(blue / 6) * 6)
    return f"#{red:02x}{green:02x}{blue:02x}"


def portrait_svg(
    cells: tuple[tuple[AsciiCell, ...], ...],
    *,
    theme: str,
    x: float,
    y: float,
    character_width: float,
    line_height: float,
    font_size: float,
) -> str:
    rendered: list[str] = []
    for row_index, row in enumerate(cells):
        baseline = y + row_index * line_height
        for column_index, cell in enumerate(row):
            if cell.character == " ":
                continue
            position = x + column_index * character_width
            rendered.append(
                f'<text class="portrait" x="{position:.1f}" y="{baseline:.1f}" '
                f'font-size="{font_size}" fill="{adjusted_color(cell, theme)}">'
                f"{html.escape(cell.character)}</text>"
            )
    return "\n".join(rendered)


def neofetch_rows_svg(
    rows: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    palette: Palette,
    start_y: int,
) -> str:
    rendered: list[str] = []
    cursor_y = start_y

    for label, values in rows:
        key = f"{label}:"
        rendered.append(
            f'<text class="row" x="590" y="{cursor_y}">'
            f'<tspan class="label" fill="{palette.label}">{html.escape(key)}</tspan>'
            f'<tspan class="value" fill="{palette.value}"> {html.escape(values[0])}</tspan>'
            "</text>"
        )
        for continuation in values[1:]:
            cursor_y += 23
            padding = " " * (len(key) + 1)
            rendered.append(
                f'<text class="row value" x="590" y="{cursor_y}" fill="{palette.value}">'
                f"{padding}{html.escape(continuation)}</text>"
            )
        cursor_y += 29

    return "\n".join(rendered)


def ansi_swatches_svg() -> str:
    rendered: list[str] = []
    for row, colors in enumerate(ANSI_SWATCHES):
        for column, color in enumerate(colors):
            rendered.append(
                f'<rect x="{590 + column * 28}" y="{430 + row * 20}" '
                f'width="28" height="20" fill="{color}"/>'
            )
    return "\n".join(rendered)


def svg_style(palette: Palette) -> str:
    return f"""
  <style>
    text {{
      fill: {palette.text};
      font-family: {FONT_STACK};
      font-style: normal;
      white-space: pre;
    }}
    .portrait {{ font-weight: 500; }}
    .label {{ fill: {palette.label}; font-weight: 600; }}
    .value {{ fill: {palette.value}; }}
    .row {{ font-size: 16px; }}
    .host {{ fill: {palette.label}; font-size: 16px; font-weight: 700; }}
    .underline {{ fill: {palette.muted}; font-size: 16px; }}
  </style>"""


def profile_svg(
    portrait: tuple[tuple[AsciiCell, ...], ...], *, theme: str, palette: Palette
) -> str:
    portrait_markup = portrait_svg(
        portrait,
        theme=theme,
        x=24,
        y=36,
        character_width=6.35,
        line_height=10.85,
        font_size=10.6,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py. The source portrait is not stored. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 600" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate. Following Bun, GPUI, and SpacetimeDB. Keep it simple, stupid.</desc>
{svg_style(palette)}
  <rect x="1" y="1" width="1178" height="598" rx="18" fill="{palette.background}" stroke="{palette.border}" stroke-width="2"/>
  <text class="row" x="24" y="20" fill="{palette.text}">~ ❯ whoami</text>
  {portrait_markup}
  <text class="host" x="590" y="52">thomas@luzivog</text>
  <text class="underline" x="590" y="77">---------------</text>
  {neofetch_rows_svg(PROFILE_ROWS, palette=palette, start_y=111)}
  {ansi_swatches_svg()}
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
    portrait = ascii_portrait(args.portrait, columns=82, rows=50)

    for theme, palette in PALETTES.items():
        (args.output / f"profile-{theme}.svg").write_text(
            profile_svg(portrait, theme=theme, palette=palette), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
