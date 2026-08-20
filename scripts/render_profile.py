#!/usr/bin/env python3
"""Render Thomas Fairhurst's responsive GitHub profile cards.

The source portrait is deliberately supplied at render time and never copied into
the repository. Only the derived monochrome ASCII portrait is embedded in the
generated SVG assets.
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
ASCII_RAMP = " .,:;irsXA253hMHGS#9B&@"


@dataclass(frozen=True)
class Palette:
    background: str
    border: str
    divider: str
    portrait: str
    text: str
    muted: str
    label: str
    signal: str


PALETTES = {
    "dark": Palette(
        background="#0d0f12",
        border="#2b3038",
        divider="#242932",
        portrait="#d7d4cf",
        text="#eee9e2",
        muted="#7f8995",
        label="#b96779",
        signal="#72cf93",
    ),
    "light": Palette(
        background="#faf8f4",
        border="#d8d1c8",
        divider="#e3ddd5",
        portrait="#504a47",
        text="#2d2927",
        muted="#8d847d",
        label="#833b4d",
        signal="#2f7d52",
    ),
}


DESKTOP_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Name", ("Thomas Fairhurst",)),
    ("Role", ("Co-founder & CTO at Leadlord",)),
    ("Building", ("Compliant marketing campaigns,", "fast and affordable")),
    ("Previously", ("PhoneHost — AI call handling for restaurants",)),
    ("Open source", ("toks · agentdictate",)),
    ("Following", ("Bun · GPUI · SpacetimeDB",)),
    ("Principle", ("Keep it simple, stupid.",)),
    ("Education", ("McGill CS → Imperial MSc Advanced Computing",)),
)

MOBILE_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Name", ("Thomas Fairhurst",)),
    ("Role", ("Co-founder & CTO at Leadlord",)),
    ("Building", ("Compliant marketing campaigns,", "fast and affordable")),
    ("Previously", ("PhoneHost — AI call handling", "for restaurants")),
    ("Open source", ("toks · agentdictate",)),
    ("Following", ("Bun · GPUI · SpacetimeDB",)),
    ("Principle", ("Keep it simple, stupid.",)),
    ("Education", ("McGill CS → Imperial MSc", "Advanced Computing")),
)


def ascii_portrait(path: Path, *, columns: int, rows: int) -> tuple[str, ...]:
    with Image.open(path) as source:
        image = source.convert("RGB")

    width, height = image.size
    # Keep the cap, face, and upper shoulders while dropping empty background.
    image = image.crop(
        (
            round(width * 0.12),
            round(height * 0.18),
            round(width * 0.995),
            round(height * 0.96),
        )
    )
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image, cutoff=(1, 2))
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Sharpness(image).enhance(2.0)
    image = image.resize((columns, rows), Image.Resampling.LANCZOS)

    rendered: list[str] = []
    for row in range(rows):
        characters: list[str] = []
        for column in range(columns):
            luminance = image.getpixel((column, row))
            if luminance < 20:
                characters.append(" ")
                continue
            normalized = min(1.0, (luminance - 20) / 235)
            ramp_index = round((normalized**1.24) * (len(ASCII_RAMP) - 1))
            characters.append(ASCII_RAMP[ramp_index])
        rendered.append("".join(characters).rstrip())

    return tuple(rendered)


def portrait_svg(
    lines: tuple[str, ...],
    *,
    color: str,
    x: int,
    y: int,
    line_height: int,
    font_size: float,
) -> str:
    spans = "\n".join(
        f'<tspan x="{x}" y="{y + index * line_height}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text class="portrait" x="{x}" y="{y}" font-size="{font_size}" fill="{color}">\n'
        f"{spans}\n"
        "</text>"
    )


def rows_svg(
    rows: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    palette: Palette,
    x: int,
    y: int,
    dots_x_offset: int,
    value_x_offset: int,
    row_gap: int,
    continuation_gap: int,
) -> tuple[str, int]:
    rendered: list[str] = []
    cursor_y = y
    for label, values in rows:
        rendered.append(
            f'<text class="row label" x="{x}" y="{cursor_y}" fill="{palette.label}">{html.escape(label)}</text>\n'
            f'<text class="row dots" x="{x + dots_x_offset}" y="{cursor_y}" fill="{palette.muted}">....</text>\n'
            f'<text class="row value" x="{x + value_x_offset}" y="{cursor_y}" fill="{palette.text}">{html.escape(values[0])}</text>'
        )
        for continuation in values[1:]:
            cursor_y += continuation_gap
            rendered.append(
                f'<text class="row value" x="{x + value_x_offset}" y="{cursor_y}" fill="{palette.text}">{html.escape(continuation)}</text>'
            )
        cursor_y += row_gap

    return "\n".join(rendered), cursor_y


def svg_style(palette: Palette, *, font_size: float) -> str:
    return f"""
  <style>
    text, tspan {{ fill: {palette.text}; font-family: {FONT_STACK}; font-style: normal; white-space: pre; }}
    .prompt, .value {{ fill: {palette.text}; }}
    .portrait {{ fill: {palette.portrait}; }}
    .label {{ fill: {palette.label}; font-weight: 600; }}
    .dots {{ fill: {palette.muted}; }}
    .row {{ font-size: {font_size}px; }}
    .signal {{ fill: {palette.signal}; }}
    .cursor {{ animation: blink 1.1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .cursor {{ animation: none; }} }}
  </style>"""


def desktop_svg(portrait: tuple[str, ...], palette: Palette) -> str:
    rows, _ = rows_svg(
        DESKTOP_ROWS,
        palette=palette,
        x=426,
        y=91,
        dots_x_offset=103,
        value_x_offset=151,
        row_gap=38,
        continuation_gap=23,
    )
    portrait_markup = portrait_svg(
        portrait,
        color=palette.portrait,
        x=21,
        y=38,
        line_height=18,
        font_size=15.2,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py. The source portrait is not stored. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 560" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate. Following Bun, GPUI, and SpacetimeDB. Keep it simple, stupid.</desc>
{svg_style(palette, font_size=15.5)}
  <rect x="1" y="1" width="1038" height="558" rx="18" fill="{palette.background}" stroke="{palette.border}" stroke-width="2"/>
  <line x1="402" y1="22" x2="402" y2="538" stroke="{palette.divider}"/>
  {portrait_markup}
  <text class="prompt" x="426" y="39" font-size="16" fill="{palette.text}">thomas@leadlord:~$ whoami</text>
  <circle cx="1004" cy="34" r="5" fill="{palette.signal}"/>
  {rows}
  <text class="prompt" x="426" y="523" font-size="16" fill="{palette.text}">thomas@leadlord:~$</text>
  <text class="signal cursor" x="607" y="523" font-size="16" fill="{palette.signal}">▮</text>
</svg>
"""


def mobile_svg(portrait: tuple[str, ...], palette: Palette) -> str:
    rows, _ = rows_svg(
        MOBILE_ROWS,
        palette=palette,
        x=20,
        y=412,
        dots_x_offset=88,
        value_x_offset=126,
        row_gap=34,
        continuation_gap=21,
    )
    portrait_markup = portrait_svg(
        portrait,
        color=palette.portrait,
        x=84,
        y=67,
        line_height=14,
        font_size=11.8,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/render_profile.py. The source portrait is not stored. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 430 880" role="img" aria-labelledby="title description">
  <title id="title">Thomas Fairhurst — GitHub profile</title>
  <desc id="description">Co-founder and CTO at Leadlord. Open-source author of toks and agentdictate. Following Bun, GPUI, and SpacetimeDB. Keep it simple, stupid.</desc>
{svg_style(palette, font_size=13.2)}
  <rect x="1" y="1" width="428" height="878" rx="16" fill="{palette.background}" stroke="{palette.border}" stroke-width="2"/>
  <text class="prompt" x="20" y="32" font-size="13.5" fill="{palette.text}">thomas@leadlord:~$ whoami</text>
  <circle cx="402" cy="27" r="4" fill="{palette.signal}"/>
  {portrait_markup}
  <line x1="20" y1="379" x2="410" y2="379" stroke="{palette.divider}"/>
  {rows}
  <text class="prompt" x="20" y="842" font-size="13.5" fill="{palette.text}">thomas@leadlord:~$</text>
  <text class="signal cursor" x="174" y="842" font-size="13.5" fill="{palette.signal}">▮</text>
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

    desktop_portrait = ascii_portrait(args.portrait, columns=46, rows=28)
    mobile_portrait = ascii_portrait(args.portrait, columns=36, rows=22)

    for theme, palette in PALETTES.items():
        (args.output / f"profile-desktop-{theme}.svg").write_text(
            desktop_svg(desktop_portrait, palette), encoding="utf-8"
        )
        (args.output / f"profile-mobile-{theme}.svg").write_text(
            mobile_svg(mobile_portrait, palette), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
