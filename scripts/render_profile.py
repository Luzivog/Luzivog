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
    divider: str
    text: str
    muted: str
    label: str
    value: str
    signal: str


@dataclass(frozen=True)
class AsciiCell:
    character: str
    color: tuple[int, int, int]
    luminance: float


PALETTES = {
    "dark": Palette(
        background="#0d0f12",
        border="#2b3038",
        divider="#242932",
        text="#eee9e2",
        muted="#7f8995",
        label="#b96779",
        value="#a5d6ff",
        signal="#72cf93",
    ),
    "light": Palette(
        background="#faf8f4",
        border="#d8d1c8",
        divider="#e3ddd5",
        text="#2d2927",
        muted="#8d847d",
        label="#833b4d",
        value="#0969da",
        signal="#2f7d52",
    ),
}


IDENTITY_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("name", ("Thomas Fairhurst",)),
    ("role", ("Co-founder & CTO at Leadlord",)),
    ("building", ("Compliant marketing campaigns,", "fast and affordable")),
)

WORK_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("previously", ("PhoneHost — AI call handling", "for restaurants")),
    ("open_source", ("toks · agentdictate",)),
)

CURRENT_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("following", ("Bun · GPUI · SpacetimeDB",)),
    ("principle", ("Keep it simple, stupid.",)),
    ("education", ("McGill CS → Imperial MSc", "Advanced Computing")),
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


def terminal_rows_svg(
    rows: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    palette: Palette,
    start_y: int,
) -> str:
    rendered: list[str] = []
    cursor_y = start_y
    value_column = 20

    for label, values in rows:
        key = f"{label}:"
        leader = "." * (value_column - len(key) - 2)
        rendered.append(
            f'<text class="row" x="590" y="{cursor_y}">'
            f'<tspan class="label" fill="{palette.label}">{html.escape(key)}</tspan>'
            f'<tspan class="dots" fill="{palette.muted}"> {leader} </tspan>'
            f'<tspan class="value" fill="{palette.value}">{html.escape(values[0])}</tspan>'
            "</text>"
        )
        for continuation in values[1:]:
            cursor_y += 23
            padding = " " * value_column
            rendered.append(
                f'<text class="row value" x="590" y="{cursor_y}" fill="{palette.value}">'
                f"{padding}{html.escape(continuation)}</text>"
            )
        cursor_y += 29

    return "\n".join(rendered)


RULE_WIDTH = 50


def rule_svg(title: str, *, y: int, palette: Palette) -> str:
    head = f"- {title} "
    rule = "-" * (RULE_WIDTH - len(head))
    return (
        f'<text class="section" x="590" y="{y}" fill="{palette.text}">'
        f"{head}<tspan class=\"dots\" fill=\"{palette.muted}\">{rule}</tspan></text>"
    )


def terminal_output_svg(palette: Palette) -> str:
    header_rule = "-" * (RULE_WIDTH - len("thomas@leadlord "))
    return f"""
  <text class="output-header" x="590" y="75" fill="{palette.text}">thomas@leadlord<tspan class="dots" fill="{palette.muted}"> {header_rule}</tspan></text>
  {terminal_rows_svg(IDENTITY_ROWS, palette=palette, start_y=110)}
  {rule_svg("work", y=246, palette=palette)}
  {terminal_rows_svg(WORK_ROWS, palette=palette, start_y=278)}
  {rule_svg("current", y=382, palette=palette)}
  {terminal_rows_svg(CURRENT_ROWS, palette=palette, start_y=414)}
""".strip()


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
    .dots {{ fill: {palette.muted}; }}
    .value {{ fill: {palette.value}; }}
    .row {{ font-size: 15.1px; }}
    .output-header, .section {{ font-size: 15.1px; }}
    .signal {{ fill: {palette.signal}; }}
    .cursor {{ animation: blink 1.1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .cursor {{ animation: none; }} }}
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
  <line x1="558" y1="22" x2="558" y2="578" stroke="{palette.divider}"/>
  {portrait_markup}
  <text class="row" x="590" y="38" fill="{palette.text}">thomas@leadlord:~$ ./profile</text>
  {terminal_output_svg(palette)}
  <text class="row" x="590" y="560" fill="{palette.text}">thomas@leadlord:~$ <tspan class="signal cursor" fill="{palette.signal}">▮</tspan></text>
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
