"""The DealRank mark, as geometry: the three ascending rounded bars from the
web app's entry gate (frontend/src/components/EntryGate.tsx), set in the
rounded square of its sidebar lockup, with the wordmark beside it. The PDF
draws it on a canvas and the PPTX as native shapes, both from these numbers,
so the two exports carry an identical logo and neither needs an image file.

Coordinates are fractions of the mark's side, measured from its bottom-left.
The bars are the web app's 24-unit glyph (x 3.5 / 10 / 16.5, width 4, heights
8.5 / 13 / 17) scaled to 56% of the square.
"""

from dataclasses import dataclass

from app.reports import theme

WORDMARK = "DealRank"

MARK_RADIUS = 0.26
BAR_RADIUS = 0.028
BAR_WIDTH = 0.0933
BASELINE = 0.3017
# (left edge, height) of each bar, shortest to tallest.
BARS = ((0.3017, 0.198), (0.4533, 0.303), (0.605, 0.397))

# Wordmark: font size as a fraction of the mark, and the gap after the mark.
WORD_SIZE = 0.62
WORD_GAP = 0.3


def mix(foreground: str, background: str, alpha: float) -> str:
    """`foreground` at `alpha` opacity over `background`, as a solid hex
    colour (the web mark's bars are one colour at 55%, 80% and 100% opacity;
    PPTX and the PDF canvas get the equivalent solids)."""
    channels = (
        round(int(foreground[i : i + 2], 16) * alpha + int(background[i : i + 2], 16) * (1 - alpha))
        for i in (0, 2, 4)
    )
    return "".join(f"{c:02X}" for c in channels)


@dataclass(frozen=True)
class Palette:
    square: str
    bars: tuple[str, str, str]
    word: str


# The sidebar lockup, for dark backgrounds: brass mark, navy bars.
DARK = Palette(
    theme.ACCENT,
    (
        mix(theme.INK, theme.ACCENT, 0.55),
        mix(theme.INK, theme.ACCENT, 0.8),
        theme.INK,
    ),
    theme.WHITE,
)
# For white pages: navy mark, white bars.
LIGHT = Palette(
    theme.INK,
    (
        mix(theme.WHITE, theme.INK, 0.55),
        mix(theme.WHITE, theme.INK, 0.8),
        theme.WHITE,
    ),
    theme.INK,
)

# Oversized bars used as quiet cover artwork, a shade off the cover colour.
ART_COLORS = ("111F33", "15263E", "1A2E4A")
